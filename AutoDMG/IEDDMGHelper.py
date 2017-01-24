# -*- coding: utf-8 -*-
#
#  IEDDMGHelper.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-19.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
import subprocess
import time
import traceback

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


class IEDDMGHelper(NSObject):
    
    def init(self):
        self = super(IEDDMGHelper, self).init()
        if self is None:
            return None
        
        # A dictionary of dmg paths and their respective mount points.
        # NB: we only handle a single mount point per dmg.
        self.dmgs = dict()
        
        return self
    
    def initWithDelegate_(self, delegate):
        self = self.init()
        if self is None:
            return None
        
        self.delegate = delegate
        
        return self
    
    # Send a message to delegate in the main thread.
    def tellDelegate_message_(self, selector, message):
        if self.delegate.respondsToSelector_(selector):
            self.delegate.performSelectorOnMainThread_withObject_waitUntilDone_(selector, message, False)

    def attachedDMGs(self):
        dmgMounts = dict()
        
        LogDebug("Finding already attached dmgs")
        p = subprocess.Popen(["/usr/bin/hdiutil",
                              "info",
                              "-plist"],
                             bufsize=1,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            errstr = "hdiutil info failed with return code %d" % p.returncode
            if err:
                errstr += ": %s" % err.decode("utf-8")
            LogWarning("%@", errstr)
            return dmgMounts
        
        # Strip EULA text.
        outXML = out[out.find(b"<?xml"):]
        outData = NSData.dataWithBytes_length_(outXML, len(outXML))
        plist, format, error = \
            NSPropertyListSerialization.propertyListWithData_options_format_error_(outData,
                                                                                   NSPropertyListImmutable,
                                                                                   None,
                                                                                   None)
        for dmgInfo in plist["images"]:
            for entity in dmgInfo.get("system-entities", []):
                try:
                    image_path = dmgInfo["image-path"]
                    alias_path = ""
                    bookmark = CFURLCreateBookmarkDataFromAliasRecord(kCFAllocatorDefault, dmgInfo["image-alias"])
                    if bookmark:
                        url, stale, error = CFURLCreateByResolvingBookmarkData(None, bookmark,
                                                                               kCFBookmarkResolutionWithoutUIMask,
                                                                               None, None, None, None)
                        if url:
                            alias_path = url.path()
                        else:
                            LogDebug("Couldn't resolve bookmark: %@", error.localizedDescription())
                    for path in set(x for x in (image_path, alias_path) if x):
                        dmgMounts[path] = entity["mount-point"]
                        LogDebug("'%@' is already mounted at '%@'", path, entity["mount-point"])
                    break
                except IndexError:
                    pass
                except KeyError:
                    pass

        return dmgMounts
    
    def hdiutilAttach_(self, args):
        try:
            dmgPath, selector = args
            
            # If the dmg is already mounted, reuse that.
            attached = self.attachedDMGs()
            if dmgPath in attached:
                LogDebug("%@ is already mounted, no need to attach", dmgPath)
                self.tellDelegate_message_(selector, {"success": True,
                                                      "dmg-path": dmgPath,
                                                      "mount-point": attached[dmgPath]})
                return
            
            LogDebug("Attaching %@", dmgPath)
            p = subprocess.Popen(["/usr/bin/hdiutil",
                                  "attach",
                                  dmgPath,
                                  "-mountRandom", "/tmp",
                                  "-nobrowse",
                                  "-noverify",
                                  "-plist"],
                                 bufsize=1,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate("Y\n")
            LogDebug("Checking result of attaching %@", dmgPath)
            if p.returncode != 0:
                errstr = "hdiutil attach failed with return code %d" % p.returncode
                if err:
                    errstr += ": %s" % err.decode("utf-8")
                self.tellDelegate_message_(selector, {"success": False,
                                                      "dmg-path": dmgPath,
                                                      "error-message": errstr})
                return
            # Strip EULA text.
            outXML = out[out.find(b"<?xml"):]
            outData = NSData.dataWithBytes_length_(outXML, len(outXML))
            plist, format, error = \
                NSPropertyListSerialization.propertyListWithData_options_format_error_(outData,
                                                                                       NSPropertyListImmutable,
                                                                                       None,
                                                                                       None)
            for partition in plist["system-entities"]:
                if partition.get("potentially-mountable") == 1:
                    if "mount-point" in partition:
                        self.dmgs[dmgPath] = partition["mount-point"]
                        break
            else:
                self.tellDelegate_message_(selector, {"success": False,
                                                      "dmg-path": dmgPath,
                                                      "error-message": "No mounted filesystem in %s" % dmgPath})
                return
            self.tellDelegate_message_(selector, {"success": True,
                                                  "dmg-path": dmgPath,
                                                  "mount-point": self.dmgs[dmgPath]})
        except Exception as e:
            try:
                exceptionInfo = traceback.format_exc()
            except:
                exceptionInfo = "(no traceback available)"
            msg = "Attach of %s crashed with exception %s:\n%s" % (dmgPath, e, exceptionInfo)
            self.tellDelegate_message_(selector, {"success": False,
                                                  "dmg-path": dmgPath,
                                                  "error-message": msg})
    
    # Attach a dmg and send a success dictionary.
    def attach_selector_(self, dmgPath, selector):
        if dmgPath in self.dmgs:
            self.tellDelegate_message_(selector, {"success": True,
                                                  "dmg-path": dmgPath,
                                                  "mount-point": self.dmgs[dmgPath]})
        else:
            self.performSelectorInBackground_withObject_(self.hdiutilAttach_, [dmgPath, selector])
    
    def hdiutilDetach_(self, args):
        try:
            dmgPath, target, selector = args
            LogDebug("Detaching %@", dmgPath)
            try:
                cmd = ["/usr/bin/hdiutil",
                       "detach",
                       self.dmgs[dmgPath]]
            except KeyError:
                target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                             {"success": False,
                                                                              "dmg-path": dmgPath,
                                                                              "error-message": "%s not mounted" % dmgPath},
                                                                             False)
                return
            del self.dmgs[dmgPath]
            maxtries = 5
            for tries in range(maxtries):
                LogDebug("Detaching %@, attempt %d/%d", dmgPath, tries + 1, maxtries)
                if tries == maxtries >> 1:
                    LogDebug("Adding -force to detach arguments")
                    cmd.append("-force")
                p = subprocess.Popen(cmd,
                                     bufsize=1,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                out, err = p.communicate()
                if p.returncode == 0:
                    target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                                 {"success": True, "dmg-path": dmgPath},
                                                                                 False)
                    return
                elif tries == maxtries - 1:
                    errstr = "hdiutil detach failed with return code %d" % p.returncode
                    if err:
                        errstr += ": %s" % err.decode("utf-8")
                    target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                                 {"success": False,
                                                                                  "dmg-path": dmgPath,
                                                                                  "error-message": errstr},
                                                                                 False)
                else:
                    time.sleep(1)
        except Exception as e:
            try:
                exceptionInfo = traceback.format_exc()
            except:
                exceptionInfo = "(no traceback available)"
            msg = "Detach of %s crashed with exception %s:\n%s" % (dmgPath, e, exceptionInfo)
            target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                         {"success": False,
                                                                          "dmg-path": dmgPath,
                                                                          "error-message": msg},
                                                                         False)
    
    # Detach a dmg and send a success dictionary.
    def detach_selector_(self, dmgPath, selector):
        if dmgPath in self.dmgs:
            self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, self.delegate, selector])
        else:
            self.tellDelegate_message_(selector, {"success": False,
                                                  "dmg-path": dmgPath,
                                                  "error-message": "%s isn't mounted" % dmgPath})
    
    # Detach all mounted dmgs and send a message with a dictionary of detach
    # failures.
    def detachAll_(self, selector):
        LogDebug("detachAll:%@", selector)
        self.detachAllFailed = dict()
        self.detachAllRemaining = len(self.dmgs)
        self.detachAllSelector = selector
        if self.dmgs:
            for dmgPath in self.dmgs.iterkeys():
                self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, self, self.handleDetachAllResult_])
        else:
            if self.delegate.respondsToSelector_(selector):
                self.delegate.performSelector_withObject_(selector, {})
    
    def handleDetachAllResult_(self, result):
        LogDebug("handleDetachAllResult:%@", result)
        if not result["success"]:
            self.detachAllFailed[result["dmg-path"]] = result["error-message"]
        self.detachAllRemaining -= 1
        if self.detachAllRemaining == 0:
            self.tellDelegate_message_(self.detachAllSelector, self.detachAllFailed)

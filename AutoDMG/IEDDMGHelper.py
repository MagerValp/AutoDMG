#-*- coding: utf-8 -*-
#
#  IEDDMGHelper.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-10-19.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
import subprocess
import plistlib
import time


class IEDDMGHelper(NSObject):
    
    def init(self):
        self = super(IEDDMGHelper, self).init()
        if self is None:
            return None
        
        # A dictionary of dmg paths and their respective mount points.
        # NB: we only handle a single mount point per dmg.
        self.dmgs = dict()
        
        return self
    
    def initWithDelegate_(self, handler):
        self = self.init()
        if self is None:
            return None
        
        self.handler = handler
        
        return self
    
    # Send a message to handler in the main thread.
    def tellHandler_message_(self, selector, message):
        if self.handler.respondsToSelector_(selector):
            self.handler.performSelectorOnMainThread_withObject_waitUntilDone_(selector, message, False)
    
    def hdiutilAttach_(self, args):
        dmgPath, selector = args
        p = subprocess.Popen([u"/usr/bin/hdiutil",
                              u"attach",
                              dmgPath,
                              u"-mountRandom", u"/tmp",
                              u"-nobrowse",
                              u"-noverify",
                              u"-plist",
                              u"-owners", u"on"],
                             bufsize=-1,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            errstr = u"hdiutil attach failed with return code %d" % p.returncode
            if err:
                errstr += u": %s" % err
            self.tellHandler_message_(selector, {u"success": False,
                                              u"dmg-path": dmgPath,
                                              u"error-message": errstr})
            return
        plist = plistlib.readPlistFromString(out)
        for partition in plist[u"system-entities"]:
            if u"mount-point" in partition:
                self.dmgs[dmgPath] = partition[u"mount-point"]
                break
        else:
            self.tellHandler_message_(selector, {u"success": False,
                                                 u"dmg-path": dmgPath,
                                                 u"error-message": u"No mounted filesystem in %s" % dmgPath})
            return
        self.tellHandler_message_(selector, {u"success": True,
                                             u"dmg-path": dmgPath,
                                             u"mount-point": self.dmgs[dmgPath]})
    
    # Attach a dmg and send a success dictionary.
    def attach_selector_(self, dmgPath, selector):
        if dmgPath in self.dmgs:
            self.tellHandler_message_(selector, {u"success": True,
                                                 u"dmg-path": dmgPath,
                                                 u"mount-point": self.dmgs[dmgPath]})
        else:
            self.performSelectorInBackground_withObject_(self.hdiutilAttach_, [dmgPath, selector])
    
    def hdiutilDetach_(self, args):
        dmgPath, selector = args
        try:
            cmd = [u"/usr/bin/hdiutil",
                   u"detach",
                   self.dmgs[dmgPath]]
        except KeyError:
            self.tellHandler_message_(selector, {u"success": False,
                                                 u"dmg-path": dmgPath,
                                                 u"error-message": u"%s not mounted" % dmgPath})
        maxtries = 5
        for tries in range(maxtries):
            if tries == maxtries >> 1:
                cmd.append(u"-force")
            p = subprocess.Popen(cmd,
                                 bufsize=-1,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            if p.returncode == 0:
                del self.dmgs[dmgPath]
                self.tellHandler_message_(selector, {u"success": True, u"dmg-path": dmgPath})
                return
            elif tries == maxtries - 1:
                errstr = u"hdiutil detach failed with return code %d" % p.returncode
                if err:
                    errstr += u": %s" % err
                self.tellHandler_message_(selector, {u"success": False,
                                                     u"dmg-path": dmgPath,
                                                     u"error-message": errstr})
            else:
                time.sleep(1)
    
    # Detach a dmg and send a success dictionary.
    def detach_selector_(self, dmgPath, selector):
        if dmgPath in self.dmgs:
            self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, selector])
        else:
            self.tellHandler_message_(selector, {u"success": False,
                                                 u"dmg-path": dmgPath,
                                                 u"error-message": u"%s isn't mounted" % dmgPath})
    
    # Detach all mounted dmgs and send a message with a dictionary of detach
    # failures.
    def detachAll_(self, selector):
        self.detachAllFailed = dict()
        self.detachAllCount = len(self.dmgs)
        self.detachAllSelector = selector
        if self.dmgs:
            for dmgPath in self.dmgs.keys():
                self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, self.handleDetachAllResult_])
        else:
            if self.handler.respondsToSelector_(selector):
                self.handler.performSelector_withObject_(selector, {})
    
    def handleDetachAllResult_(self, result):
        if result[u"success"] == False:
            self.detachAllFailed[result[u"dmg-path"]] = result[u"error-message"]
        self.detachAllCount -= 1
        if self.detachAllCount == 0:
            self.tellHandler_message_(self.detachAllSelector, self.detachAllFailed)

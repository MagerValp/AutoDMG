#-*- coding: utf-8 -*-
#
#  IEDDMGHelper.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-19.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
import subprocess
import plistlib
import time

from IEDLog import *


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
    
    def hdiutilAttach_(self, args):
        dmgPath, selector = args
        LogDebug(u"Attaching %@", dmgPath)
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
                errstr += u": %s" % err.decode(u"utf-8")
            self.tellDelegate_message_(selector, {u"success": False,
                                                  u"dmg-path": dmgPath,
                                                  u"error-message": errstr})
            return
        plist = plistlib.readPlistFromString(out)
        for partition in plist[u"system-entities"]:
            if u"mount-point" in partition:
                self.dmgs[dmgPath] = partition[u"mount-point"]
                break
        else:
            self.tellDelegate_message_(selector, {u"success": False,
                                                  u"dmg-path": dmgPath,
                                                  u"error-message": u"No mounted filesystem in %s" % dmgPath})
            return
        self.tellDelegate_message_(selector, {u"success": True,
                                              u"dmg-path": dmgPath,
                                              u"mount-point": self.dmgs[dmgPath]})
    
    # Attach a dmg and send a success dictionary.
    def attach_selector_(self, dmgPath, selector):
        if dmgPath in self.dmgs:
            self.tellDelegate_message_(selector, {u"success": True,
                                                  u"dmg-path": dmgPath,
                                                  u"mount-point": self.dmgs[dmgPath]})
        else:
            self.performSelectorInBackground_withObject_(self.hdiutilAttach_, [dmgPath, selector])
    
    def hdiutilDetach_(self, args):
        dmgPath, target, selector = args
        LogDebug(u"Detaching %@", dmgPath)
        try:
            cmd = [u"/usr/bin/hdiutil",
                   u"detach",
                   self.dmgs[dmgPath]]
        except KeyError:
            target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                         {u"success": False,
                                                                          u"dmg-path": dmgPath,
                                                                          u"error-message": u"%s not mounted" % dmgPath},
                                                                         False)
            return
        del self.dmgs[dmgPath]
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
                target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                             {u"success": True, u"dmg-path": dmgPath},
                                                                             False)
                return
            elif tries == maxtries - 1:
                errstr = u"hdiutil detach failed with return code %d" % p.returncode
                if err:
                    errstr += u": %s" % err.decode(u"utf-8")
                target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                             {u"success": False,
                                                                              u"dmg-path": dmgPath,
                                                                              u"error-message": errstr},
                                                                             False)
            else:
                time.sleep(1)
    
    # Detach a dmg and send a success dictionary.
    def detach_selector_(self, dmgPath, selector):
        if dmgPath in self.dmgs:
            self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, self.delegate, selector])
        else:
            self.tellDelegate_message_(selector, {u"success": False,
                                                  u"dmg-path": dmgPath,
                                                  u"error-message": u"%s isn't mounted" % dmgPath})
    
    # Detach all mounted dmgs and send a message with a dictionary of detach
    # failures.
    def detachAll_(self, selector):
        LogDebug(u"detachAll:%@", selector)
        self.detachAllFailed = dict()
        self.detachAllRemaining = len(self.dmgs)
        self.detachAllSelector = selector
        if self.dmgs:
            for dmgPath in self.dmgs.keys():
                self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, self, self.handleDetachAllResult_])
        else:
            if self.delegate.respondsToSelector_(selector):
                self.delegate.performSelector_withObject_(selector, {})
    
    def handleDetachAllResult_(self, result):
        LogDebug(u"handleDetachAllResult:%@", result)
        if result[u"success"] == False:
            self.detachAllFailed[result[u"dmg-path"]] = result[u"error-message"]
        self.detachAllRemaining -= 1
        if self.detachAllRemaining == 0:
            self.tellDelegate_message_(self.detachAllSelector, self.detachAllFailed)

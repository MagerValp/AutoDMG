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


IEDDMGHelperDebug = False


class IEDDMGHelper(NSObject):
    
    def init(self):
        self = super(IEDDMGHelper, self).init()
        if self is None:
            return None
        
        # A dictionary of dmg paths and their respective mount points.
        # NB: we only handle a single mount point per dmg.
        self.dmgs = dict()
        
        return self
    
    def hdiutilAttach_(self, args):
        dmgPath, target, selector = args
        if IEDDMGHelperDebug: (u"hdiutilAttach:%@", dmgPath)
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
            target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                         {u"success": False,
                                                                           u"dmg-path": dmgPath,
                                                                           u"error-message": errstr},
                                                                          False)
            return
        plist = plistlib.readPlistFromString(out)
        if IEDDMGHelperDebug: (u"plist = %@", plist)
        for partition in plist[u"system-entities"]:
            if u"mount-point" in partition:
                self.dmgs[dmgPath] = partition[u"mount-point"]
                if IEDDMGHelperDebug: (u"self.dmgs = %@", self.dmgs)
                break
        else:
            target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                         {u"success": False,
                                                                          u"dmg-path": dmgPath,
                                                                          u"error-message": u"No mounted filesystem in %s" % dmgPath},
                                                                         False)
            return
        target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                     {u"success": True,
                                                                      u"dmg-path": dmgPath,
                                                                      u"mount-point": self.dmgs[dmgPath]},
                                                                     False)
    
    # Attach a dmg and send the target a success dictionary.
    def attach_withTarget_selector_(self, dmgPath, target, selector):
        if IEDDMGHelperDebug: (u"attach_withTarget_selector_")
        if dmgPath in self.dmgs:
            target.performSelector_withObject_(selector, {u"success": True,
                                                          u"dmg-path": dmgPath,
                                                          u"mount-point": self.dmgs[dmgPath]})
        else:
            self.performSelectorInBackground_withObject_(self.hdiutilAttach_, [dmgPath, target, selector])
    
    def hdiutilDetach_(self, args):
        dmgPath, target, selector = args
        if IEDDMGHelperDebug: (u"hdiutilDetach:%@", dmgPath)
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
        maxtries = 5
        for tries in range(maxtries):
            if tries == maxtries >> 1:
                cmd.append(u"-force")
            p = subprocess.Popen(cmd,
                                 bufsize=-1,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
            if IEDDMGHelperDebug: (u"%@ returned %d", cmd, p.returncode)
            if p.returncode == 0:
                del self.dmgs[dmgPath]
                target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                             {u"success": True,
                                                                              u"dmg-path": dmgPath},
                                                                             False)
                return
            elif tries == maxtries - 1:
                errstr = u"hdiutil detach failed with return code %d" % p.returncode
                if err:
                    errstr += u": %s" % err
                target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                             {u"success": False,
                                                                              u"dmg-path": dmgPath,
                                                                              u"error-message": errstr},
                                                                             False)
            else:
                time.sleep(1)
    
    # Detach a dmg and send the target a success dictionary.
    def detach_withTarget_selector_(self, dmgPath, target, selector):
        if IEDDMGHelperDebug: (u"detach_withTarget_selector_")
        if dmgPath in self.dmgs:
            self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, target, selector])
        else:
            target.performSelector_withObject_(selector, {u"success": False,
                                                          u"dmg-path": dmgPath,
                                                          u"error-message": u"%s isn't mounted" % dmgPath})
    
    # Detach all mounted dmgs and send the target a message with a dictionary
    # of detach failures.
    def detachAllWithTarget_selector_(self, target, selector):
        if IEDDMGHelperDebug: (u"detachAllWithTarget_selector_")
        self.detachAllFailed = dict()
        self.detachAllCount = len(self.dmgs)
        self.detachAllTarget = target
        self.detachAllSelector = selector
        if self.dmgs:
            for dmgPath in self.dmgs.keys():
                self.performSelectorInBackground_withObject_(self.hdiutilDetach_, [dmgPath, self, self.handleDetachAllResult_])
        else:
            target.performSelector_withObject_(selector, {})
    
    def handleDetachAllResult_(self, result):
        if IEDDMGHelperDebug: (u"handleDetachAllResult_")
        if result[u"success"] == False:
            self.detachAllFailed[result[u"dmg-path"]] = result[u"error-message"]
        self.detachAllCount -= 1
        if self.detachAllCount == 0:
            self.detachAllTarget.performSelectorOnMainThread_withObject_waitUntilDone_(self.detachAllSelector,
                                                                                       self.detachAllFailed,
                                                                                       False)

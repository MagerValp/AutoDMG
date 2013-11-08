#-*- coding: utf-8 -*-
#
#  IEDAppDelegate.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright Per Olofsson, University of Gothenburg 2013. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet, __version__ as pyObjCVersion

from IEDLog import *
from IEDUtil import *
import platform


defaults = NSUserDefaults.standardUserDefaults()


class IEDAppDelegate(NSObject):
    
    mainWindowController = IBOutlet()
    appVersionController = IBOutlet()
    
    def init(self):
        self = super(IEDAppDelegate, self).init()
        if self is None:
            return None
        
        return self
    
    def initialize(self):
        # Log version info on startup.
        version, build = IEDUtil.getAppVersion()
        LogNotice(u"AutoDMG v%@ build %@", version, build)
        name, version, build = IEDUtil.readSystemVersion_(u"/")
        LogNotice(u"%@ %@ %@", name, version, build)
        LogNotice(u"%@ %@ (%@)", platform.python_implementation(),
                                 platform.python_version(),
                                 platform.python_compiler())
        LogNotice(u"PyObjC %@", pyObjCVersion)
        
        # Initialize user defaults before application starts.
        defaultsPath = NSBundle.mainBundle().pathForResource_ofType_(u"Defaults", u"plist")
        defaultsDict = NSDictionary.dictionaryWithContentsOfFile_(defaultsPath)
        defaults.registerDefaults_(defaultsDict)
    
    def applicationDidFinishLaunching_(self, sender):
        updateProfileInterval = defaults.integerForKey_(u"UpdateProfileInterval")
        if updateProfileInterval:
            lastCheck = defaults.objectForKey_(u"LastUpdateProfileCheck")
            if lastCheck.timeIntervalSinceNow() < -60 * 60 * 18:
                self.mainWindowController.updateController.checkForProfileUpdates_(self)
        
        appVersionCheckInterval = defaults.integerForKey_(u"AppVersionCheckInterval")
        if appVersionCheckInterval:
            lastCheck = defaults.objectForKey_(u"LastAppVersionCheck")
            if lastCheck.timeIntervalSinceNow() < -60 * 60 * 18:
                self.appVersionController.checkForAppUpdateSilently_(True)
    
    def applicationShouldTerminate_(self, sender):
        LogDebug(u"applicationShouldTerminate:")
        if self.mainWindowController.isBusy():
            alert = NSAlert.alloc().init()
            alert.setAlertStyle_(NSCriticalAlertStyle)
            alert.setMessageText_(u"Application busy")
            alert.setInformativeText_(u"Quitting now could leave the " \
                                      u"system in an unpredictable state.")
            alert.addButtonWithTitle_(u"Quit")
            alert.addButtonWithTitle_(u"Stay")
            button = alert.runModal()
            if button == NSAlertSecondButtonReturn:
                return NSTerminateCancel
        return NSTerminateNow
    
    def applicationWillTerminate_(self, sender):
        LogDebug(u"applicationWillTerminate:")
        self.mainWindowController.cleanup()
    
    @IBAction
    def showHelp_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(defaults.stringForKey_(u"HelpURL")))
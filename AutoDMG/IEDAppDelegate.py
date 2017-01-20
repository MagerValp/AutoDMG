# -*- coding: utf-8 -*-
#
#  IEDAppDelegate.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet, __version__ as pyObjCVersion

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage, LogException
from IEDUtil import *
import platform


defaults = NSUserDefaults.standardUserDefaults()


class IEDAppDelegate(NSObject):
    
    mainWindowController = IBOutlet()
    appVersionController = IBOutlet()
    helpMenuItem = IBOutlet()
    
    def init(self):
        self = super(IEDAppDelegate, self).init()
        if self is None:
            return None
        
        return self
    
    def initialize(self):
        # Log version info on startup.
        version, build = IEDUtil.getAppVersion()
        LogInfo("AutoDMG v%@ build %@", version, build)
        name, version, build = IEDUtil.readSystemVersion_("/")
        LogInfo("%@ %@ %@", name, version, build)
        LogInfo("%@ %@ (%@)", platform.python_implementation(),
                               platform.python_version(),
                               platform.python_compiler())
        LogInfo("PyObjC %@", pyObjCVersion)
        
        # Initialize user defaults before application starts.
        defaultsPath = NSBundle.mainBundle().pathForResource_ofType_("Defaults", "plist")
        defaultsDict = NSDictionary.dictionaryWithContentsOfFile_(defaultsPath)
        defaults.registerDefaults_(defaultsDict)
    
    def applicationDidFinishLaunching_(self, sender):
        NSApplication.sharedApplication().disableRelaunchOnLogin()
        version, build = IEDUtil.getAppVersion()
        if version.lower().endswith("b"):
            NSApplication.sharedApplication().dockTile().setBadgeLabel_("beta")
        updateProfileInterval = defaults.integerForKey_("UpdateProfileInterval")
        if updateProfileInterval:
            lastCheck = defaults.objectForKey_("LastUpdateProfileCheck")
            if lastCheck.timeIntervalSinceNow() < -60 * 60 * 18:
                self.mainWindowController.updateController.checkForProfileUpdatesSilently()
        
        appVersionCheckInterval = defaults.integerForKey_("AppVersionCheckInterval")
        if appVersionCheckInterval:
            lastCheck = defaults.objectForKey_("LastAppVersionCheck")
            if lastCheck.timeIntervalSinceNow() < -60 * 60 * 18:
                self.appVersionController.checkForAppUpdateSilently_(True)
    
    def applicationShouldTerminate_(self, sender):
        LogDebug("applicationShouldTerminate:")
        if self.mainWindowController.busy():
            alert = NSAlert.alloc().init()
            alert.setAlertStyle_(NSCriticalAlertStyle)
            alert.setMessageText_("Application busy")
            alert.setInformativeText_("Quitting now could leave the "
                                      "system in an unpredictable state.")
            alert.addButtonWithTitle_("Quit")
            alert.addButtonWithTitle_("Stay")
            button = alert.runModal()
            if button == NSAlertSecondButtonReturn:
                return NSTerminateCancel
        return NSTerminateNow
    
    def applicationWillTerminate_(self, sender):
        LogDebug("applicationWillTerminate:")
        self.mainWindowController.cleanup()
    
    @LogException
    @IBAction
    def showHelp_(self, sender):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(defaults.stringForKey_("HelpURL")))
    
    
    
    # Trampolines for document handling.
    
    @LogException
    @IBAction
    def saveDocument_(self, sender):
        LogDebug("saveDocument:")
        self.mainWindowController.saveTemplate()
    
    @LogException
    @IBAction
    def saveDocumentAs_(self, sender):
        LogDebug("saveDocumentAs:")
        self.mainWindowController.saveTemplateAs()
    
    @LogException
    @IBAction
    def openDocument_(self, sender):
        LogDebug("openDocument:")
        self.mainWindowController.openTemplate()
    
    def validateMenuItem_(self, menuItem):
        if menuItem == self.helpMenuItem:
            return True
        else:
            return not self.mainWindowController.busy()
    
    def application_openFile_(self, application, filename):
        return self.mainWindowController.openTemplateAtURL_(NSURL.fileURLWithPath_(filename))

#-*- coding: utf-8 -*-
#
#  IEDController.py
#  InstallESDtoDMG
#
#  Created by Pelle on 2013-09-19.
#  Copyright Per Olofsson, University of Gothenburg 2013. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

import os.path
import subprocess


class IEDController(NSObject):
    
    window = IBOutlet()
    
    sourceView = IBOutlet()
    sourceLabel = IBOutlet()
    
    profileDropdown = IBOutlet()
    
    destinationView = IBOutlet()
    destinationLabel = IBOutlet()
    
    buildButton = IBOutlet()
    
    buildProgressBar = IBOutlet()
    
    progress = None
    
    def awakeFromNib(self):
        self.sourceView.setDelegate_(self)
        self.buildProgressBar.setMaxValue_(100.0)
    
    def acceptSource_(self, path):
        icon = NSWorkspace.sharedWorkspace().iconForFile_(path)
        icon.setSize_(NSMakeSize(256.0, 256.0))
        self.sourceView.setImage_(icon)
        self.sourceLabel.setStringValue_(os.path.basename(path))
        #name, version, build = self.checkInstaller_(path)
        self.setUIEnabled_(True)
    
    def setUIEnabled_(self, enabled):
        self.buildButton.setEnabled_(enabled)
        self.profileDropdown.setEnabled_(enabled)
    
    def updateProgress(self):
        if self.progress is None:
            self.buildProgressBar.setIndeterminate_(True)
            self.buildProgressBar.startAnimation_(self)
        else:
            self.buildProgressBar.setIndeterminate_(False)
            self.buildProgressBar.setDoubleValue_(self.progress)
    
    def updateProgressMessage_(self, message):
        if message.object() == u"progress":
            self.progress = message.userInfo()[u"percent"]
            self.updateProgress()
        else:
            NSLog("Got updateProgressMesage")
            NSLog("    name:%@", message.name())
            NSLog("    object:%@", message.object())
            NSLog("    userInfo:%@", message.userInfo())
        
    
    def startTaskProgress(self):
        self.setUIEnabled_(False)
        self.progress = None
        self.updateProgress()
        dnc = NSDistributedNotificationCenter.defaultCenter()
        dnc.addObserver_selector_name_object_(self,
                                              u"updateProgressMessage:",
                                              u"se.gu.it.IEDUpdate",
                                              None)
    
    def stopTaskProgress(self):
        dnc = NSDistributedNotificationCenter.defaultCenter()
        dnc.removeObserver_name_object_(self,
                                        u"se.gu.it.IEDUpdate",
                                        None)
        self.progress = 100.0
        self.updateProgress()
        self.setUIEnabled_(True)
    
    @IBAction
    def buildButtonClicked_(self, sender):
        panel = NSSavePanel.savePanel()
        panel.setExtensionHidden_(False)
        panel.setAllowedFileTypes_([u"dmg"])
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        exists, error = panel.URL().checkResourceIsReachableAndReturnError_(None)
        if exists:
            success, error = NSFileManager.defaultManager().removeItemAtURL_error_(panel.URL(), None)
            if not success:
                NSApp.presentError_(error)
                return
        
        self.destinationLabel.setStringValue_(os.path.basename(panel.URL().path()))
        
        self.buildImageFrom_to_(self.sourceView.selectedSource, panel.URL().path())
    
    def buildImageFrom_to_(self, sourcePath, destinationPath):
        self.startTaskProgress()
        
        if os.fork() == 0:
            p = subprocess.Popen([NSBundle.mainBundle().pathForResource_ofType_(u"progresswatcher", u"py")],
                                 cwd=NSBundle.mainBundle().resourcePath())
            p.communicate()
            if p.returncode != 0:
                NSLog(u"progresswatcher exited with return code %d", ret)







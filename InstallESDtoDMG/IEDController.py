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
    
    def startTask(self):
        self.setUIEnabled_(False)
        self.progress = None
        self.updateProgress()
    
    def stopTask(self):
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
        
        self.performSelectorInBackground_withObject_(u"buildImage:",
                                                     [self.sourceView.selectedSource,
                                                      panel.URL().path()])
    
    # This runs in a background thread.
    def buildImage_(self, args):
        # Unpack arguments.
        sourcePath, destinationPath = args
        
        # Start task.
        self.performSelectorOnMainThread_withObject_waitUntilDone_(u"startTask",
                                                                   None,
                                                                   False)
        # Perform task.
        self.do_build(sourcePath, destinationPath)
        
        # Stop task.
        self.performSelectorOnMainThread_withObject_waitUntilDone_(u"stopTask",
                                                                   None,
                                                                   False)
    
    # This should call our PrivilegedHelper via launchd but for now let's just
    # kick it off with do shell script.
    def do_build(self, sourcePath, destinationPath):
        scriptPath = u"/Users/pelle/Dropbox/prog/InstallESDtoDMG/installesdtodmg.sh"
        NSLog(scriptPath)
        
        p = subprocess.Popen([u"/usr/bin/osascript", "-"],
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
        # Generate a shell script.
        shellScript = u"'%s' '%s' '%s'" % (scriptPath, sourcePath, destinationPath)
        # Wrap it in AppleScript to get admin prompt.
        appleScript = u"do shell script \"%s\" with administrator privileges" % shellScript
        # Send it to osascript's stdin.
        out, err = p.communicate(appleScript)
        if p.returncode:
            NSLog(u"build script exited with %d", p.returncode)
            return

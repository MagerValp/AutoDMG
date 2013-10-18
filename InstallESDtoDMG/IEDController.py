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

import os
from IEDSocketListener import *


class IEDController(NSObject):
    
    window = IBOutlet()
    
    sourceView = IBOutlet()
    sourceLabel = IBOutlet()
    
    profileDropdown = IBOutlet()
    
    destinationView = IBOutlet()
    destinationLabel = IBOutlet()
    
    buildButton = IBOutlet()
    
    buildProgressBar = IBOutlet()
    buildProgressMessage = IBOutlet()
    
    progress = None
    listenerDir = u"/tmp"
    listenerName = u"se.gu.it.IEDSocketListener"
    listener = None
    listenerPath = None
    
    def awakeFromNib(self):
        self.sourceView.setDelegate_(self)
        self.buildProgressBar.setMaxValue_(100.0)
        self.buildProgressMessage.setStringValue_(u"")
        self.openListenerSocket()
    
    def windowWillClose_(self, notification):
        self.closeListenerSocket()
    
    def openListenerSocket(self):
        self.listener = IEDSocketListener.alloc().init()
        self.listenerPath = self.listener.listenOnSocketInDir_withName_target_action_(self.listenerDir,
                                                                                      self.listenerName,
                                                                                      self,
                                                                                      u"handleProgressNotification:")
    
    def closeListenerSocket(self):
        self.listener.stopListening()
        try:
            os.unlink(self.listenerPath)
        except BaseException as e:
            NSLog(u"Couldn't remove listener socket %@: %@", self.listenerPath, unicode(e))
    
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
    
    def notifySuccess_(self, path):
        self.progress = 100.0
        self.updateProgress()
        self.buildProgressBar.stopAnimation_(self)
        self.setUIEnabled_(True)
        fileURL = NSURL.fileURLWithPath_(path)
        NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_([fileURL])
    
    def notifyFailure_(self, message):
        self.buildProgressBar.setIndeterminate_(False)
        self.buildProgressBar.stopAnimation_(self)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(u"Build failed")
        alert.setInformativeText_(message)
        alert.runModal()
        self.setUIEnabled_(True)
    
    def updateProgressMessage_(self, message):
        self.buildProgressMessage.setStringValue_(message)
    
    def handleProgressNotification_(self, args):
        if args[u"action"] == u"update_progressbar":
            self.progress = args[u"percent"]
            self.updateProgress()
        elif args[u"action"] == u"update_message":
            self.updateProgressMessage_(args[u"message"])
        elif args[u"action"] == u"notify_success":
            self.notifySuccess_(args[u"path"])
        elif args[u"action"] == u"notify_failure":
            self.notifyFailure_(args[u"message"])
        elif args[u"action"] == u"task_done":
            self.stopTaskProgress()
            if args[u"termination_status"] != 0:
                NSLog(u"task exited with status %@", args[u"termination_status"])
        else:
            NSLog(u"Unknown progress notification action %@", args[u"action"])
    
    def startTaskProgress(self):
        self.setUIEnabled_(False)
        self.progress = None
        self.updateProgress()
    
    def stopTaskProgress(self):
        #self.progress = 100.0
        #self.updateProgress()
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
        args = [
            NSBundle.mainBundle().pathForResource_ofType_(u"progresswatcher", u"py"),
            u"--cd",
            NSBundle.mainBundle().resourcePath(),
            self.listenerPath,
            sourcePath,
            destinationPath,
        ]
        self.performSelectorInBackground_withObject_(self.launchScript_, args)
    
    def launchScript_(self, args):
        shellscript = u' & " " & '.join(u"quoted form of arg%d" % i for i in range(len(args)))
        applescript = u"\n".join([u'set arg%d to "%s"' % (i, arg) for i, arg in enumerate(args)] + \
                                 [u'do shell script %s with administrator privileges' % shellscript])
        trampoline = NSAppleScript.alloc().initWithSource_(applescript)
        evt, error = trampoline.executeAndReturnError_(None)
        if evt is None:
            NSLog(u"NSAppleScript failed with error: %@", error)



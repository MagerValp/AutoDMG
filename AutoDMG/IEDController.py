#-*- coding: utf-8 -*-
#
#  IEDController.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright Per Olofsson, University of Gothenburg 2013. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

import os.path
from IEDLog import *
from IEDUpdateController import *
from IEDWorkflow import *


class IEDController(NSObject):
    
    mainWindow = IBOutlet()
    
    sourceBox = IBOutlet()
    sourceImage = IBOutlet()
    sourceLabel = IBOutlet()
    
    updateController = IBOutlet()
    addPkgController = IBOutlet()
    logController = IBOutlet()
    
    buildButton = IBOutlet()
    
    buildProgressWindow = IBOutlet()
    buildProgressPhase = IBOutlet()
    buildProgressBar = IBOutlet()
    buildProgressMessage = IBOutlet()
    buildProgressStopButton = IBOutlet()
    
    def awakeFromNib(self):
        LogDebug(u"awakeFromNib")
        
        # Initialize UI.
        self.buildProgressBar.setMaxValue_(100.0)
        self.buildProgressMessage.setStringValue_(u"")
        self.sourceLabel.setStringValue_(u"")
        
        # We're a delegate for the drag and drop target, protocol:
        #   (void)acceptInstaller:(NSString *)path
        self.sourceBox.setDelegate_(self)
        self.sourceImage.setDelegate_(self)
        self.sourceLabel.setDelegate_(self)
        
        # We're a delegate for the update controller, protocol:
        #   (void)updateControllerChanged
        self.updateController.setDelegate_(self)
        
        # Main workflow logic.
        self.workflow = IEDWorkflow.alloc().initWithDelegate_(self)
        
        # Enabled state for main window.
        self.enabled = True
    
    def applicationShouldTerminate_(self, sender):
        LogDebug(u"applicationShouldTerminate:")
        self.workflow.cleanup()
        return NSTerminateNow
    
    # Helper methods.
    
    def displayAlert_text_(self, message, text):
        LogDebug(u"Displaying alert: %@ (%@)", message, text)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(message)
        alert.setInformativeText_(text)
        alert.runModal()
    
    def disableMainWindowControls(self):
        self.enabled = False
        self.sourceBox.stopAcceptingDrag()
        self.sourceImage.stopAcceptingDrag()
        self.sourceLabel.stopAcceptingDrag()
        self.updateController.disableControls()
        self.addPkgController.disableControls()
        self.buildButton.setEnabled_(False)
    
    def enableMainWindowControls(self):
        self.enabled = True
        self.sourceBox.startAcceptingDrag()
        self.sourceImage.startAcceptingDrag()
        self.sourceLabel.startAcceptingDrag()
        self.updateController.enableControls()
        self.addPkgController.enableControls()
        self.updateBuildButton()
    
    def updateBuildButton(self):
        buildEnabled = self.enabled and \
                       self.workflow.hasSource() and \
                       self.updateController.allUpdatesDownloaded()
        self.buildButton.setEnabled_(buildEnabled)
    
    
    
    # Common workflow delegate methods.
    
    def detachFailed_details_(self, dmgPath, details):
        self.displayAlert_text_(u"Failed to detach %s" % dmgPath, details)
    
    
    
    # Act on user dropping an installer.
    
    def acceptSource_(self, path):
        self.disableMainWindowControls()
        self.workflow.setSource_(path)
    
    # Workflow delegate methods.
    
    def ejectingSource(self):
        self.sourceImage.setAlphaValue_(0.5)
        self.sourceLabel.setStringValue_(u"\u00a0\u00a0Ejecting…")
    
    def examiningSource_(self, path):
        icon = NSWorkspace.sharedWorkspace().iconForFile_(path)
        icon.setSize_(NSMakeSize(256.0, 256.0))
        self.sourceImage.setImage_(icon)
        self.sourceImage.setAlphaValue_(1.0)
        self.sourceLabel.setStringValue_(u"Examining…")
    
    def sourceSucceeded_(self, info):
        self.installerName = info[u"name"]
        self.installerVersion = info[u"version"]
        self.installerBuild = info[u"build"]
        self.sourceLabel.setStringValue_(u"%s %s %s" % (info[u"name"], info[u"version"], info[u"build"]))
        self.updateController.loadProfileForVersion_build_(info[u"version"], info[u"build"])
        self.enableMainWindowControls()
    
    def sourceFailed_text_(self, message, text):
        self.displayAlert_text_(message, text)
        self.sourceImage.setImage_(NSImage.imageNamed_(u"Installer Placeholder"))
        self.sourceImage.setAlphaValue_(1.0)
        self.sourceLabel.setStringValue_(u"")
    
    
    
    # Act on update controller changing.
    
    def updateControllerChanged(self):
        if self.enabled:
            self.updateBuildButton()
    
    
    
    # Act on build button.
    
    @IBAction
    def buildButtonClicked_(self, sender):
        panel = NSSavePanel.savePanel()
        panel.setExtensionHidden_(False)
        panel.setAllowedFileTypes_([u"dmg"])
        imageName = u"osx"
        formatter = NSDateFormatter.alloc().init()
        formatter.setDateFormat_(u"yyMMdd")
        if self.updateController.packagesToInstall():
            dateStr = formatter.stringFromDate_(self.updateController.profileController.publicationDate)
            imageName = u"osx_updated_%s" % dateStr
        if self.addPkgController.packagesToInstall():
            dateStr = formatter.stringFromDate_(NSDate.date())
            imageName = u"osx_custom_%s" % dateStr
        panel.setNameFieldStringValue_(u"%s-%s-%s.hfs" % (imageName, self.installerVersion, self.installerBuild))
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        exists, error = panel.URL().checkResourceIsReachableAndReturnError_(None)
        if exists:
            success, error = NSFileManager.defaultManager().removeItemAtURL_error_(panel.URL(), None)
            if not success:
                NSApp.presentError_(error)
                return
        
        self.workflow.setPackagesToInstall_(self.updateController.packagesToInstall() + \
                                            self.addPkgController.packagesToInstall())
        self.workflow.setOutputPath_(panel.URL().path())
        self.workflow.start()
    
    # Workflow delegate methods.
    
    def buildStartingWithOutput_(self, outputPath):
        self.buildProgressWindow.setTitle_(os.path.basename(outputPath))
        self.buildProgressPhase.setStringValue_(u"Starting")
        self.buildProgressBar.setIndeterminate_(True)
        self.buildProgressBar.startAnimation_(self)
        self.buildProgressBar.setDoubleValue_(0.0)
        self.buildProgressMessage.setStringValue_(u"")
        self.buildProgressWindow.makeKeyAndOrderFront_(self)
        self.disableMainWindowControls()
    
    def buildSetTotalWeight_(self, totalWeight):
        self.buildProgressBar.setMaxValue_(totalWeight)
    
    def buildSetPhase_(self, phase):
        self.buildProgressPhase.setStringValue_(phase)
    
    def buildSetProgress_(self, progress):
        self.buildProgressBar.setDoubleValue_(progress)
        self.buildProgressBar.setIndeterminate_(False)
    
    def buildSetProgressMessage_(self, message):
        self.buildProgressMessage.setStringValue_(message)
    
    def buildSucceeded(self):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(u"Build successful")
        alert.setInformativeText_(u"Built %s" % os.path.basename(self.workflow.outputPath()))
        alert.addButtonWithTitle_(u"OK")
        alert.addButtonWithTitle_(u"Reveal")
        button = alert.runModal()
        if button == NSAlertSecondButtonReturn:
            fileURL = NSURL.fileURLWithPath_(self.workflow.outputPath())
            NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_([fileURL])
    
    def buildFailed_details_(self, message, details):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(message)
        alert.setInformativeText_(details)
        alert.addButtonWithTitle_(u"OK")
        alert.addButtonWithTitle_(u"View Log")
        button = alert.runModal()
        if button == NSAlertSecondButtonReturn:
            self.logController.displayLogWindow_(self)
    
    def buildStopped(self):
        self.buildProgressWindow.orderOut_(self)
        self.enableMainWindowControls()
    



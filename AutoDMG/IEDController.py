# -*- coding: utf-8 -*-
#
#  IEDController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright 2013-2014 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

import os.path
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage, LogException
from IEDUpdateController import *
from IEDWorkflow import *
from IEDTemplate import *


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
    
    fileMenu = IBOutlet()
    openMenuItem = IBOutlet()
    saveMenuItem = IBOutlet()
    saveAsMenuItem = IBOutlet()
    
    advancedWindow = IBOutlet()
    volumeName = IBOutlet()
    volumeSize = IBOutlet()
    
    def awakeFromNib(self):
        LogDebug(u"awakeFromNib")
        
        # Initialize UI.
        self.buildProgressBar.setMaxValue_(100.0)
        self.buildProgressMessage.setStringValue_(u"")
        
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
        
        # When busy is true quitting gets a confirmation prompt.
        self._busy = False
        
        # Currently loaded template.
        self.templateURL = None
    
    # Methods to communicate with app delegate.
    
    def cleanup(self):
        self.workflow.cleanup()
    
    def busy(self):
        return self._busy
    
    def setBusy_(self, busy):
        self._busy = busy
        if busy:
            self.disableMainWindowControls()
        else:
            self.enableMainWindowControls()
    
    # Helper methods.
    
    def validateMenuItem_(self, menuItem):
        if self.busy():
            if menuItem in (self.openMenuItem,
                            self.saveMenuItem,
                            self.saveAsMenuItem):
                return False
        return True
    
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
        self.setBusy_(True)
        self.workflow.setSource_(path)
    
    # Workflow delegate methods.
    
    def ejectingSource(self):
        self.sourceImage.animator().setAlphaValue_(0.5)
        self.sourceLabel.setStringValue_(u"Ejecting")
        self.sourceLabel.setTextColor_(NSColor.disabledControlTextColor())
    
    def examiningSource_(self, path):
        self.foundSourceForIcon_(path)
        self.sourceLabel.setStringValue_(u"Examining")
        self.sourceLabel.setTextColor_(NSColor.disabledControlTextColor())
    
    def foundSourceForIcon_(self, path):
        icon = NSWorkspace.sharedWorkspace().iconForFile_(path)
        icon.setSize_(NSMakeSize(256.0, 256.0))
        tiff = icon.TIFFRepresentation()
        image = NSImage.alloc().initWithData_(tiff)
        self.sourceImage.animator().setAlphaValue_(1.0)
        self.sourceImage.animator().setImage_(image)
    
    def sourceSucceeded_(self, info):
        self.installerName = info[u"name"]
        self.installerVersion = info[u"version"]
        self.installerBuild = info[u"build"]
        self.sourceLabel.setStringValue_(u"%s %s %s" % (info[u"name"], info[u"version"], info[u"build"]))
        self.sourceLabel.setTextColor_(NSColor.controlTextColor())
        self.updateController.loadProfileForVersion_build_(info[u"version"], info[u"build"])
        template = info[u"template"]
        if template:
            LogInfo(u"Template found in image: %@", repr(template))
            # Don't default to applying updates to an image that was built
            # with updates applied, and vice versa.
            if template.applyUpdates:
                self.updateController.applyUpdatesCheckbox.setState_(NSOffState)
            else:
                self.updateController.applyUpdatesCheckbox.setState_(NSOnState)
        else:
            if info[u"sourceType"] == IEDWorkflow.SYSTEM_IMAGE:
                LogInfo(u"No template found in image")
                # If the image doesn't have a template inside, assume that updates
                # were applied.
                self.updateController.applyUpdatesCheckbox.setState_(NSOffState)
        self.setBusy_(False)
    
    def sourceFailed_text_(self, message, text):
        self.displayAlert_text_(message, text)
        self.sourceImage.animator().setImage_(NSImage.imageNamed_(u"Installer Placeholder"))
        self.sourceImage.animator().setAlphaValue_(1.0)
        self.sourceLabel.setStringValue_(u"Drop OS X Installer Here")
        self.sourceLabel.setTextColor_(NSColor.disabledControlTextColor())
        self.setBusy_(False)
    
    
    
    # Act on update controller changing.
    
    def updateControllerChanged(self):
        if self.enabled:
            self.updateBuildButton()
    
    
    
    # Act on user showing log window.
    
    @LogException
    @IBAction
    def displayAdvancedWindow_(self, sender):
        self.advancedWindow.makeKeyAndOrderFront_(self)
    
    
    
    # Act on build button.
    
    @LogException
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
        
        # Create a template to save inside the image.
        template = IEDTemplate.alloc().init()
        template.setSourcePath_(self.workflow.source())
        if self.updateController.packagesToInstall():
            template.setApplyUpdates_(True)
        else:
            template.setApplyUpdates_(False)
        if not template.setAdditionalPackages_([x.path() for x in self.addPkgController.packagesToInstall()]):
            self.displayAlert_text_(u"Additional packages failed verification",
                                    u"Check the log for details.")
            return
        template.setOutputPath_(panel.URL().path())
        if self.volumeName.stringValue():
            template.setVolumeName_(self.volumeName.stringValue())
            self.workflow.setVolumeName_(self.volumeName.stringValue().strip())
        if self.volumeSize.stringValue():
            template.setVolumeSize_(self.volumeSize.intValue())
            self.workflow.setVolumeSize_(self.volumeSize.intValue())
        self.workflow.setTemplate_(template)
        
        self.workflow.setPackagesToInstall_(self.updateController.packagesToInstall() +
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
        self.setBusy_(True)
    
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
        self.setBusy_(False)
    
    
    
    # Load and save templates.
    
    def saveTemplate(self):
        if self.templateURL:
            self.saveTemplateToURL_(self.templateURL)
        else:
            self.saveTemplateAs()
    
    def saveTemplateAs(self):
        panel = NSSavePanel.savePanel()
        panel.setExtensionHidden_(False)
        panel.setAllowedFileTypes_([u"adtmpl"])
        formatter = NSDateFormatter.alloc().init()
        formatter.setDateFormat_(u"yyMMdd")
        dateStr = formatter.stringFromDate_(NSDate.date())
        panel.setNameFieldStringValue_(u"AutoDMG-%s.adtmpl" % (dateStr))
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        exists, error = panel.URL().checkResourceIsReachableAndReturnError_(None)
        if exists:
            success, error = NSFileManager.defaultManager().removeItemAtURL_error_(panel.URL(), None)
            if not success:
                NSApp.presentError_(error)
                return
        
        self.saveTemplateToURL_(panel.URL())
    
    def saveTemplateToURL_(self, url):
        LogDebug(u"saveTemplateToURL:%@", url)
        self.templateURL = url
        NSDocumentController.sharedDocumentController().noteNewRecentDocumentURL_(url)
        
        # Create a template from the current state.
        template = IEDTemplate.alloc().init()
        if self.workflow.source():
            template.setSourcePath_(self.workflow.source())
        if self.updateController.packagesToInstall():
            template.setApplyUpdates_(True)
        else:
            template.setApplyUpdates_(False)
        if self.volumeName.stringValue():
            template.setVolumeName_(self.volumeName.stringValue())
        template.setAdditionalPackages_([x.path() for x in self.addPkgController.packagesToInstall()])
        
        error = template.saveTemplateAndReturnError_(url.path())
        if error:
            self.displayAlert_text_(u"Couldn't save template", error)
    
    def openTemplate(self):
        panel = NSOpenPanel.openPanel()
        panel.setExtensionHidden_(False)
        panel.setAllowedFileTypes_([u"adtmpl"])
        
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        return self.openTemplateAtURL_(panel.URL())
    
    def openTemplateAtURL_(self, url):
        LogDebug(u"openTemplateAtURL:%@", url)
        self.templateURL = None
        template = IEDTemplate.alloc().init()
        error = template.loadTemplateAndReturnError_(url.path())
        if error:
            self.displayAlert_text_(u"Couldn't open template", error)
            return False
        self.templateURL = url
        NSDocumentController.sharedDocumentController().noteNewRecentDocumentURL_(url)
        # AdditionalPackages.
        LogDebug(u"Setting additional packages to %@", template.additionalPackages)
        self.addPkgController.replacePackagesWithPaths_(template.additionalPackages)
        # ApplyUpdates.
        if template.applyUpdates:
            LogDebug(u"Enable updates")
            self.updateController.applyUpdatesCheckbox.setState_(NSOnState)
        else:
            LogDebug(u"Disable updates")
            self.updateController.applyUpdatesCheckbox.setState_(NSOffState)
        # VolumeName.
        self.volumeName.setStringValue_(u"")
        if template.volumeName:
            LogDebug(u"Setting volume name to %@", template.volumeName)
            self.volumeName.setStringValue_(template.volumeName)
        # VolumeSize.
        self.volumeSize.setStringValue_(u"")
        if template.volumeSize:
            LogDebug(u"Setting volume size to %@", template.volumeSize)
            self.volumeSize.setIntValue_(template.volumeSize)
        # SourcePath.
        if template.sourcePath:
            LogDebug(u"Setting source to %@", template.sourcePath)
            self.setBusy_(True)
            self.workflow.setSource_(template.sourcePath)
        return True

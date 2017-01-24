# -*- coding: utf-8 -*-
#
#  IEDUpdateController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
from objc import IBAction, IBOutlet
import Quartz

from IEDProfileController import *
from IEDUpdateCache import *
from IEDPackage import *
from IEDUtil import *
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage, LogException


class IEDUpdateController(NSObject):
    
    profileController = IBOutlet()
    
    updateBox = IBOutlet()
    
    applyUpdatesCheckbox = IBOutlet()
    updateTable = IBOutlet()
    updateTableImage = IBOutlet()
    updateTableLabel = IBOutlet()
    downloadButton = IBOutlet()
    
    downloadWindow = IBOutlet()
    downloadLabel = IBOutlet()
    downloadProgressBar = IBOutlet()
    downloadStopButton = IBOutlet()
    
    updateBoxHeight = IBOutlet()
    
    def init(self):
        self = super(IEDUpdateController, self).init()
        if self is None:
            return None
        
        self.cache = IEDUpdateCache.alloc().initWithDelegate_(self)
        self.updates = list()
        self.downloadTotalSize = 0
        self.downloads = list()
        self.delegate = None
        self.version = None
        self.build = None
        self.profileWarning = None
        self.boxTableSizeDelta = 0
        
        return self
    
    def setDelegate_(self, delegate):
        self.delegate = delegate
    
    def awakeFromNib(self):
        self.cachedImage = NSImage.imageNamed_("Package")
        self.uncachedImage = NSImage.imageNamed_("Package blue arrow")
        
        self.updatesAllOKImage = NSImage.imageNamed_("Checkmark")
        self.updatesToDownloadImage = NSImage.imageNamed_("Download")
        self.updatesWarningImage = NSImage.imageNamed_("Exclamation")
        self.updateTableImage.setImage_(None)
        self.updateTableLabel.setStringValue_("")
        self.updateTable.setDataSource_(self)
        
        self.boxTableSizeDelta = self.updateBox.frame().size.height - self.updateTable.frame().size.height
        
        self.updateHeight()
    
    def validateMenuItem_(self, menuItem):
        return not self.delegate.busy()
    
    # Helper methods.
    
    def updateHeight(self):
        rowHeight = 18
        rows = self.numberOfRowsInTableView_(self.updateTable)
        height = rows * rowHeight
        height = max(min(height, int(6.5 * rowHeight)), 3.5 * rowHeight)
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.15)
        easeInEaseOut = Quartz.CAMediaTimingFunction.functionWithName_(Quartz.kCAMediaTimingFunctionEaseInEaseOut)
        NSAnimationContext.currentContext().setTimingFunction_(easeInEaseOut)
        self.updateBoxHeight.animator().setConstant_(height + self.boxTableSizeDelta)
        NSAnimationContext.endGrouping()
        
    
    def disableControls(self):
        LogDebug("disableControls")
        self.applyUpdatesCheckbox.setEnabled_(False)
        self.updateTable.setEnabled_(False)
        self.downloadButton.setEnabled_(False)
    
    def enableControls(self):
        LogDebug("enableControls")
        self.applyUpdatesCheckbox.setEnabled_(len(self.updates) > 0)
        self.updateTable.setEnabled_(len(self.updates) > 0)
        self.downloadButton.setEnabled_(len(self.downloads) > 0)
    
    def showRemainingDownloads(self):
        if self.profileWarning:
            self.updateTableImage.setImage_(self.updatesWarningImage)
            self.updateTableLabel.setStringValue_(self.profileWarning)
            self.updateTableLabel.setTextColor_(NSColor.controlTextColor())
            return
        
        if len(self.downloads) == 0:
            self.updateTableLabel.setStringValue_("All updates downloaded")
            self.updateTableLabel.setTextColor_(NSColor.disabledControlTextColor())
            self.updateTableImage.setImage_(self.updatesAllOKImage)
        else:
            sizeStr = IEDUtil.formatByteSize_(self.downloadTotalSize)
            plurals = "s" if len(self.downloads) >= 2 else ""
            downloadLabel = "%d update%s to download (%s)" % (len(self.downloads), plurals, sizeStr)
            self.updateTableLabel.setStringValue_(downloadLabel)
            self.updateTableLabel.setEnabled_(True)
            self.updateTableLabel.setTextColor_(NSColor.controlTextColor())
            self.updateTableImage.setImage_(self.updatesToDownloadImage)
    
    def countDownloads(self):
        LogDebug("countDownloads")
        self.downloads = list()
        self.downloadTotalSize = 0
        for package in self.updates:
            if self.cache.isCached_(package.sha1()):
                package.setImage_(self.cachedImage)
            else:
                package.setImage_(self.uncachedImage)
                self.downloadTotalSize += package.size()
                self.downloads.append(package)
        self.updateTable.reloadData()
        self.showRemainingDownloads()
        self.updateHeight()
    
    # External state of controller.
    
    def allUpdatesDownloaded(self):
        if self.applyUpdatesCheckbox.state() == NSOffState:
            return True
        return len(self.downloads) == 0
    
    def packagesToInstall(self):
        if self.applyUpdatesCheckbox.state() == NSOffState:
            return []
        return self.updates
    
    
    
    # Act on profile update requested.
    
    @LogException
    @IBAction
    def checkForProfileUpdates_(self, sender):
        self.silent = False
        self.doCheckForProfileUpdates()
    
    def checkForProfileUpdatesSilently(self):
        self.silent = True
        self.doCheckForProfileUpdates()
    
    def doCheckForProfileUpdates(self):
        LogInfo("Checking for updates")
        self.dateBeforeUpdating = self.profileController.publicationDate
        self.disableControls()
        defaults = NSUserDefaults.standardUserDefaults()
        url = NSURL.URLWithString_(defaults.stringForKey_("UpdateProfilesURL"))
        self.profileController.updateFromURL_(url)
    
    @LogException
    @IBAction
    def cancelProfileUpdateCheck_(self, sender):
        self.profileController.cancelUpdateDownload()
    
    # IEDProfileController delegate methods.
    
    def profileUpdateAllDone(self):
        self.enableControls()
        if not self.silent:
            alert = NSAlert.alloc().init()
            formatter = NSDateFormatter.alloc().init()
            formatter.setDateFormat_("yyyy-MM-dd HH.mm")
            dateStr = formatter.stringFromDate_(self.profileController.publicationDate)
            if self.dateBeforeUpdating != self.profileController.publicationDate:
                alert.setMessageText_("Profile updated")
                alert.setInformativeText_("Publication date: %s" % dateStr)
            else:
                alert.setMessageText_("No profile update available")
                alert.setInformativeText_("Last update: %s" % dateStr)
            alert.runModal()
    
    def profileUpdateFailed_(self, error):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(error.localizedDescription())
        alert.setInformativeText_(error.userInfo()[NSErrorFailingURLStringKey])
        alert.runModal()
        self.silent = True
    
    def profileUpdateSucceeded_(self, publicationDate):
        LogDebug("profileUpdateSucceeded:%@", publicationDate)
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setObject_forKey_(NSDate.date(), "LastUpdateProfileCheck")
    
    def profilesUpdated(self):
        LogDebug("profilesUpdated")
        self.cache.pruneAndCreateSymlinks(self.profileController.updatePaths)
        if self.version or self.build:
            self.loadProfileForVersion_build_(self.version, self.build)
    
    # Load update profile.
    
    def loadProfileForVersion_build_(self, version, build):
        LogDebug("loadProfileForVersion:%@ build:%@", version, build)
        self.version = version
        self.build = build
        self.updates = list()
        profile = self.profileController.profileForVersion_Build_(version, build)
        if profile is None:
            # No update profile for this build, try to figure out why.
            self.profileWarning = self.profileController.whyNoProfileForVersion_build_(version, build)
        else:
            if self.profileController.deprecatedOS:
                self.profileWarning = "No longer updated by Apple"
            else:
                self.profileWarning = None
            for update in profile:
                package = IEDPackage.alloc().init()
                package.setName_(update["name"])
                package.setPath_(self.cache.updatePath_(update["sha1"]))
                package.setSize_(update["size"])
                package.setUrl_(update["url"])
                package.setSha1_(update["sha1"])
                # Image is set by countDownloads().
                self.updates.append(package)
        self.countDownloads()
    
    
    
    # Act on apply updates checkbox changing.
    
    @LogException
    @IBAction
    def applyUpdatesCheckboxChanged_(self, sender):
        if self.delegate:
            self.delegate.updateControllerChanged()
    
    
    
    # Act on download button being clicked.
    
    @LogException
    @IBAction
    def downloadButtonClicked_(self, sender):
        self.disableControls()
        self.downloadLabel.setStringValue_("")
        self.downloadProgressBar.setIndeterminate_(True)
        self.downloadWindow.makeKeyAndOrderFront_(self)
        self.downloadCounter = 0
        self.downloadNumUpdates = len(self.downloads)
        self.cache.downloadUpdates_(self.downloads)
    
    # Act on download stop button being clicked.
    
    @LogException
    @IBAction
    def downloadStopButtonClicked_(self, sender):
        self.cache.stopDownload()
    
    # UpdateCache delegate methods.
    
    def downloadAllDone(self):
        LogDebug("downloadAllDone")
        self.downloadWindow.orderOut_(self)
        self.countDownloads()
        self.enableControls()
        if self.delegate:
            self.delegate.updateControllerChanged()
    
    def downloadStarting_(self, package):
        LogDebug("downloadStarting:")
        self.downloadProgressBar.setIndeterminate_(False)
        self.downloadProgressBar.setDoubleValue_(0.0)
        self.downloadProgressBar.setMaxValue_(package.size())
        self.downloadCounter += 1
        self.downloadLabel.setStringValue_("%s (%s)" % (package.name(), IEDUtil.formatByteSize_(package.size())))
    
    def downloadStarted_(self, package):
        LogDebug("downloadStarted:")
        self.downloadStopButton.setEnabled_(True)
    
    def downloadStopped_(self, package):
        LogDebug("downloadStopped:")
        self.downloadStopButton.setEnabled_(False)
    
    def downloadGotData_bytesRead_(self, package, bytes):
        self.downloadProgressBar.setDoubleValue_(bytes)
    
    def downloadSucceeded_(self, package):
        LogDebug("downloadSucceeded:")
        self.countDownloads()
        if self.delegate:
            self.delegate.updateControllerChanged()
    
    def downloadFailed_withError_(self, package, message):
        LogDebug("downloadFailed:withError:")
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Download failed")
        alert.setInformativeText_(message)
        alert.runModal()
    
    
    
    # We're an NSTableViewDataSource.
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.updates)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        # FIXME: Use bindings.
        if column.identifier() == "image":
            return self.updates[row].image()
        elif column.identifier() == "name":
            return self.updates[row].name()

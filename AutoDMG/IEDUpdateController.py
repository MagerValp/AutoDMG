#-*- coding: utf-8 -*-
#
#  IEDUpdateController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
from objc import IBAction, IBOutlet

from IEDProfileController import *
from IEDUpdateCache import *
from IEDPackage import *


def IEDFormatBytes(bytes):
    bytes = float(bytes)
    unitIndex = 0
    while len(str(int(bytes))) > 3:
        bytes /= 1000.0
        unitIndex += 1
    return u"%.1f %s" % (bytes, (u"bytes", u"kB", u"MB", u"GB", u"TB")[unitIndex])


class IEDUpdateController(NSObject):
    
    profileController = IBOutlet()
    
    applyUpdatesCheckbox = IBOutlet()
    updateTable = IBOutlet()
    updateTableImage = IBOutlet()
    updateTableLabel = IBOutlet()
    downloadButton = IBOutlet()
    
    downloadWindow = IBOutlet()
    downloadLabel = IBOutlet()
    downloadProgressBar = IBOutlet()
    downloadStopButton = IBOutlet()
    
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
        
        return self
    
    def setDelegate_(self, delegate):
        self.delegate = delegate
    
    def awakeFromNib(self):
        self.cachedImage = NSImage.imageNamed_(u"Package")
        self.uncachedImage = NSImage.imageNamed_(u"Package blue arrow")
        
        self.updatesAllOKImage = NSImage.imageNamed_(u"Checkmark")
        self.updatesToDownloadImage = NSImage.imageNamed_(u"Download")
        self.updatesWarningImage = NSImage.imageNamed_(u"Exclamation")
        self.updateTableImage.setImage_(None)
        self.updateTableLabel.setStringValue_(u"")
        self.updateTable.setDataSource_(self)
    
    # Helper methods.
    
    def disableControls(self):
        LogDebug(u"disableControls")
        self.applyUpdatesCheckbox.setEnabled_(False)
        self.updateTable.setEnabled_(False)
        self.downloadButton.setEnabled_(False)
    
    def enableControls(self):
        LogDebug(u"enableControls")
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
            self.updateTableLabel.setStringValue_(u"All updates downloaded")
            self.updateTableLabel.setTextColor_(NSColor.disabledControlTextColor())
            self.updateTableImage.setImage_(self.updatesAllOKImage)
        else:
            sizeStr = IEDFormatBytes(self.downloadTotalSize)
            plurals = u"s" if len(self.downloads) >= 2 else u""
            downloadLabel = u"%d update%s to download (%s)" % (len(self.downloads), plurals, sizeStr)
            self.updateTableLabel.setStringValue_(downloadLabel)
            self.updateTableLabel.setEnabled_(True)
            self.updateTableLabel.setTextColor_(NSColor.controlTextColor())
            self.updateTableImage.setImage_(self.updatesToDownloadImage)
    
    def countDownloads(self):
        LogDebug(u"countDownloads")
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
    
    @IBAction
    def checkForProfileUpdates_(self, sender):
        LogInfo(u"Checking for updates")
        self.disableControls()
        defaults = NSUserDefaults.standardUserDefaults()
        url = NSURL.URLWithString_(defaults.stringForKey_(u"UpdateProfilesURL"))
        self.profileController.updateFromURL_(url)
    
    @IBAction
    def cancelProfileUpdateCheck_(self, sender):
        self.profileController.cancelUpdateDownload()
    
    # IEDProfileController delegate methods.
    
    def profileUpdateAllDone(self):
        self.enableControls()
    
    def profileUpdateFailed_(self, error):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(error.localizedDescription())
        alert.setInformativeText_(error.userInfo()[NSErrorFailingURLStringKey])
        alert.runModal()
    
    def profileUpdateSucceeded_(self, publicationDate):
        LogDebug(u"profileUpdateSucceeded:%@", publicationDate)
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setObject_forKey_(NSDate.date(), u"LastUpdateProfileCheck")
    
    def profilesUpdated(self):
        LogDebug(u"profilesUpdated")
        self.cache.pruneAndCreateSymlinks(self.profileController.updatePaths)
        if self.version or self.build:
            self.loadProfileForVersion_build_(self.version, self.build)
    
    # Load update profile.
    
    def loadProfileForVersion_build_(self, version, build):
        LogDebug(u"loadProfileForVersion:%@ build:%@", version, build)
        self.version = version
        self.build = build
        self.updates = list()
        profile = self.profileController.profileForVersion_Build_(version, build)
        if profile is None:
            # No update profile for this build, try to figure out why.
            self.profileWarning = self.profileController.whyNoProfileForVersion_build_(version, build)
        else:
            self.profileWarning = None
            for update in profile:
                package = IEDPackage.alloc().init()
                package.setName_(update[u"name"])
                package.setPath_(self.cache.updatePath_(update[u"sha1"]))
                package.setSize_(update[u"size"])
                package.setUrl_(update[u"url"])
                package.setSha1_(update[u"sha1"])
                # Image is set by countDownloads().
                self.updates.append(package)
        self.countDownloads()
    
    
    
    # Act on apply updates checkbox changing.
    
    @IBAction
    def applyUpdatesCheckboxChanged_(self, sender):
        if self.delegate:
            self.delegate.updateControllerChanged()
    
    
    
    # Act on download button being clicked.
    
    @IBAction
    def downloadButtonClicked_(self, sender):
        self.disableControls()
        self.downloadLabel.setStringValue_(u"")
        self.downloadProgressBar.setIndeterminate_(True)
        self.downloadWindow.makeKeyAndOrderFront_(self)
        self.downloadCounter = 0
        self.downloadNumUpdates = len(self.downloads)
        self.cache.downloadUpdates_(self.downloads)
    
    # Act on download stop button being clicked.
    
    @IBAction
    def downloadStopButtonClicked_(self, sender):
        self.cache.stopDownload()
    
    # UpdateCache delegate methods.
    
    def downloadAllDone(self):
        LogDebug(u"downloadAllDone")
        self.downloadWindow.orderOut_(self)
        self.countDownloads()
        self.enableControls()
        if self.delegate:
            self.delegate.updateControllerChanged()
    
    def downloadStarting_(self, package):
        LogDebug(u"downloadStarting:")
        self.downloadProgressBar.setIndeterminate_(False)
        self.downloadProgressBar.setDoubleValue_(0.0)
        self.downloadProgressBar.setMaxValue_(package.size())
        self.downloadCounter += 1
        self.downloadLabel.setStringValue_(u"%s (%s)" % (package.name(), IEDFormatBytes(package.size())))
    
    def downloadStarted_(self, package):
        LogDebug(u"downloadStarted:")
        self.downloadStopButton.setEnabled_(True)
    
    def downloadStopped_(self, package):
        LogDebug(u"downloadStopped:")
        self.downloadStopButton.setEnabled_(False)
    
    def downloadGotData_bytesRead_(self, package, bytes):
        self.downloadProgressBar.setDoubleValue_(bytes)
    
    def downloadSucceeded_(self, package):
        LogDebug(u"downloadSucceeded:")
        self.countDownloads()
        if self.delegate:
            self.delegate.updateControllerChanged()
    
    def downloadFailed_withError_(self, package, message):
        LogDebug(u"downloadFailed:withError:")
        alert = NSAlert.alloc().init()
        alert.setMessageText_(u"Download failed")
        alert.setInformativeText_(message)
        alert.runModal()
    
    
    
    # We're an NSTableViewDataSource.
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.updates)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        # FIXME: Use bindings.
        if column.identifier() == u"image":
            return self.updates[row].image()
        elif column.identifier() == u"name":
            return self.updates[row].name()



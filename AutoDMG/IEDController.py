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
from objc import IBAction, IBOutlet, nil

import os
import grp
import platform
import subprocess
from IEDSocketListener import *
from IEDDMGHelper import *
from IEDProfileController import *
from IEDUpdateCache import *
from IEDUpdateTableDataSource import *
from IEDPackageTableDataSource import *


IEDTaskNone = 0
IEDTaskInstall = 1
IEDTaskImageScan = 2


class IEDController(NSObject):
    
    mainWindow = IBOutlet()
    
    sourceView = IBOutlet()
    sourceLabel = IBOutlet()
    
    applyUpdatesCheckbox = IBOutlet()
    updateTable = IBOutlet()
    updateTableLabel = IBOutlet()
    downloadButton = IBOutlet()
    
    additionalPackagesTable = IBOutlet()
    
    buildButton = IBOutlet()
    
    progressWindow = IBOutlet()
    buildProgressFilename = IBOutlet()
    buildProgressBar = IBOutlet()
    buildProgressMessage = IBOutlet()
    
    downloadWindow = IBOutlet()
    downloadLabel = IBOutlet()
    downloadProgressBar = IBOutlet()
    
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
        self.dmgHelper = IEDDMGHelper.alloc().init()
        
        # Updates.
        self.profileController = IEDProfileController.alloc().init()
        self.updateCache = IEDUpdateCache.alloc().init()
        utc = IEDUpdateTableDataSource.alloc()
        self.updateTableDataSource = utc.initWithProfileController_updateCache_(self.profileController,
                                                                                self.updateCache)
        self.updateTable.setDataSource_(self.updateTableDataSource)
        
        # Additional packages.
        self.packageTableDataSource = IEDPackageTableDataSource.alloc().init()
        self.additionalPackagesTable.setDataSource_(self.packageTableDataSource)
        self.additionalPackagesTable.registerForDraggedTypes_([NSFilenamesPboardType, NSStringPboardType])
        
        self.installerMountPoint = None
        self.currentTask = IEDTaskNone
        self.packagesToInstall = list()
    
    def windowWillClose_(self, notification):
        self.closeListenerSocket()
        self.dmgHelper.detachAllWithTarget_selector_(nil, nil)
    
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
    
    def failSourceWithMessage_informativeText_(self, message, text):
        self.setUIEnabled_(False)
        alert = NSAlert.alloc().init()
        alert.setMessageText_(message)
        alert.setInformativeText_(text)
        alert.runModal()
        self.sourceView.setImage_(NSImage.imageNamed_(u"Installer Placeholder"))
        self.sourceLabel.setStringValue_(u"")
        self.installerMountPoint = None
        self.dmgHelper.detachAllWithTarget_selector_(self, self.displayFailedUnmounts_)
    
    def displayFailedUnmounts_(self, failedUnmounts):
        #NSLog(u"displayFailedUnmounts_")
        if failedUnmounts:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(u"Failed to eject dmgs")
            text = u"\n".join(u"%s: %s" % (dmg, error) for dmg, error in failedUnmounts.iteritems())
            alert.setInformativeText_(text)
            alert.runModal()
    
    # Manage updates.
    
    @IBAction
    def downloadButtonClicked_(self, sender):
        self.downloadButton.setEnabled_(False)
        self.downloadLabel.setStringValue_(u"")
        self.downloadProgressBar.setIndeterminate_(True)
        self.downloadWindow.makeKeyAndOrderFront_(self)
        self.downloadCounter = 0
        self.downloadNumUpdates = len(self.updateTableDataSource.downloads)
        self.updateCache.downloadUpdates_withTarget_selector_(self.updateTableDataSource.downloads,
                                                              self,
                                                              self.notifyDownload_)
    
    def notifyDownload_(self, message):
        if message[u"action"] == u"start":
            self.downloadProgressBar.setIndeterminate_(False)
            self.downloadProgressBar.setDoubleValue_(0.0)
            self.downloadCounter += 1
            update = message[u"update"]
            self.downloadLabel.setStringValue_(u"%d/%d: %s" % (self.downloadCounter,
                                                               self.downloadNumUpdates,
                                                               update[u"name"]))
        elif message[u"action"] == u"alldone":
            self.downloadWindow.orderOut_(self)
            self.updateDownloadState_(True)
        elif message[u"action"] == u"failed":
            alert = NSAlert.alertWithError_(message[u"error"])
            alert.runModal()
        elif message[u"action"] == u"response":
            pass
        elif message[u"action"] == u"data":
            percent = 100.0 * message[u"bytes-received"] / message[u"update"][u"size"]
            self.downloadProgressBar.setDoubleValue_(percent)
        elif message[u"action"] == u"checksumming":
            self.downloadProgressBar.setIndeterminate_(True)
        elif message[u"action"] == u"checksum-ok":
            self.updateDownloadState_(False)
        elif message[u"action"] == u"checksum-failed":
            pass
        else:
            NSLog(u"notifyDownload: Unrecognized message action: %@", message)
    
    def updateDownloadState_(self, enableButton):
        self.updateTableDataSource.countDownloads()
        self.updateTable.reloadData()
        if len(self.updateTableDataSource.downloads) == 0:
            self.updateTableLabel.setStringValue_(u"All updates downloaded")
            self.updateTableLabel.setTextColor_(NSColor.disabledControlTextColor())
            self.downloadButton.setEnabled_(False)
        else:
            niceSize = float(self.updateTableDataSource.downloadTotalSize)
            unitIndex = 0
            while len(str(int(niceSize))) > 3:
                niceSize /= 1000.0
                unitIndex += 1
            sizeStr = u"%.1f %s" % (niceSize, (u"bytes", u"kB", u"MB", u"GB", u"TB")[unitIndex])
            plurals = u"s" if len(self.updateTableDataSource.downloads) >= 2 else u""
            downloadLabel = u"%d update%s to download (%s)" % (len(self.updateTableDataSource.downloads), plurals, sizeStr)
            self.updateTableLabel.setStringValue_(downloadLabel)
            self.updateTableLabel.setTextColor_(NSColor.controlTextColor())
            self.downloadButton.setEnabled_(enableButton)
    
    # A long chain of methods to accept a new dropped installer.
    
    def acceptSource_(self, path):
        #NSLog(u"acceptSource_")
        self.installerAppPath = path
        self.setUIEnabled_(False)
        if self.installerMountPoint:
            self.sourceView.setAlphaValue_(0.5)
            self.sourceLabel.setStringValue_(u"Ejecting…")
        self.installerMountPoint = None
        self.dmgHelper.detachAllWithTarget_selector_(self, self.continueAcceptAfterEject_)
    
    def continueAcceptAfterEject_(self, failedUnmounts):
        self.displayFailedUnmounts_(failedUnmounts)
        #NSLog(u"continueAcceptAfterEject_")
        self.sourceLabel.setStringValue_(u"Examining…")
        icon = NSWorkspace.sharedWorkspace().iconForFile_(self.installerAppPath)
        icon.setSize_(NSMakeSize(256.0, 256.0))
        self.sourceView.setImage_(icon)
        self.sourceView.setAlphaValue_(1.0)
        installESDPath = os.path.join(self.installerAppPath, u"Contents/SharedSupport/InstallESD.dmg")
        self.dmgHelper.attach_withTarget_selector_(installESDPath, self, self.handleSourceMountResult_)
    
    def handleSourceMountResult_(self, result):
        #NSLog(u"handleSourceMount_")
        if result[u"success"] == False:
            self.failSourceWithMessage_informativeText_(u"Failed to mount %s" % result[u"dmg-path"],
                                                        result[u"error-message"])
            return
        # Don't set this again since 10.9 mounts BaseSystem.dmg after InstallESD.dmg.
        # FIXME: check Packages/OSInstall.mpkg
        if self.installerMountPoint is None:
            self.installerMountPoint = result[u"mount-point"]
        mountPoint = result[u"mount-point"]
        versionPlistPath = u"System/Library/CoreServices/SystemVersion.plist"
        if os.path.exists(os.path.join(mountPoint, versionPlistPath)):
            # InstallESD.dmg for 10.7/10.8, BaseSystem.dmg for 10.9.
            plistData = NSData.dataWithContentsOfFile_(os.path.join(mountPoint, versionPlistPath))
            plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(plistData,
                                                                                                          NSPropertyListImmutable,
                                                                                                          None,
                                                                                                          None)
            name = plist[u"ProductName"]
            version = plist[u"ProductUserVisibleVersion"]
            build = plist[u"ProductBuildVersion"]
            installerVersion = tuple(int(x) for x in version.split(u"."))
            runningVersion = tuple(int(x) for x in platform.mac_ver()[0].split(u"."))
            if installerVersion[:2] == runningVersion[:2]:
                self.installerName = name
                self.installerVersion = version
                self.installerBuild = build
                self.sourceLabel.setStringValue_(u"%s %s %s" % (name, version, build))
                self.setUIEnabled_(True)
                if result[u"dmg-path"].endswith(u"BaseSystem.dmg"):
                    self.dmgHelper.detach_withTarget_selector_(result[u"dmg-path"],
                                                               self,
                                                               self.handleDetachResult_)
                self.updateTableDataSource.loadProfileForVersion_build_(version, build)
                self.updateDownloadState_(True)
            else:
                self.failSourceWithMessage_informativeText_(u"Version mismatch",
                                                            u"The major version of the installer and the current OS must match.")
        elif os.path.exists(os.path.join(mountPoint, u"BaseSystem.dmg")):
            # Go down into BaseSystem.dmg to find the version for 10.9 installers.
            self.dmgHelper.attach_withTarget_selector_(os.path.join(mountPoint, u"BaseSystem.dmg"), self, self.handleSourceMountResult_)
        else:
            self.failSourceWithMessage_informativeText_(u"Invalid installer",
                                                        u"Couldn't find system version in InstallESD.")
    
    def handleDetachResult_(self, result):
        if result[u"success"] == False:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(u"Failed to detach %s" % result[u"dmg-path"])
            alert.setInformativeText_(result[u"error-message"])
            alert.runModal()
    
    def setUIEnabled_(self, enabled):
        self.mainWindow.standardWindowButton_(NSWindowCloseButton).setEnabled_(enabled)
        self.buildButton.setEnabled_(enabled)
    
    def updateProgress(self):
        if self.progress is None:
            self.buildProgressBar.setIndeterminate_(True)
            self.buildProgressBar.startAnimation_(self)
        else:
            self.buildProgressBar.setIndeterminate_(False)
            self.buildProgressBar.setDoubleValue_(self.progress)
    
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
    
    def updatePackageProgressName_num_(self, name, num):
        self.packageNum = num
        self.packageName = name
        NSLog(u"Installing package %d/%d: %@", num + 1, len(self.packagesToInstall), name)
    
    def handleProgressNotification_(self, args):
        if args[u"action"] == u"update_progressbar":
            self.progress = args[u"percent"]
            self.updateProgress()
        elif args[u"action"] == u"update_message":
            self.updateProgressMessage_(args[u"message"])
        elif args[u"action"] == u"select_package":
            self.updatePackageProgressName_num_(args[u"name"], args[u"num"])
        elif args[u"action"] == u"update_package_progress":
            if self.packageNum > 0:
                previousPackagesSize = sum(pkg[u"size"] for pkg in self.packagesToInstall[0:self.packageNum])
            else:
                previousPackagesSize = 0.0
            self.progress = 100.0 * (args[u"percent"] * self.packagesToInstall[self.packageNum][u"size"] / 100.0 + previousPackagesSize) / self.totalPackagesSize
            self.updateProgress()
        elif args[u"action"] == u"notify_failure":
            self.notifyFailure_(args[u"message"])
        elif args[u"action"] == u"task_done":
            self.stopTaskProgress()
            if args[u"termination_status"] != 0:
                NSLog(u"task exited with status %@", args[u"termination_status"])
                if self.currentTask != IEDTaskInstall:
                    self.notifyFailure_(u"Task exited with status %@", args[u"termination_status"])
            else:
                self.startNextTask()
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
        panel.setNameFieldStringValue_(u"%s_%s_%s.hfs" % (u"baseos", self.installerVersion, self.installerBuild))
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        exists, error = panel.URL().checkResourceIsReachableAndReturnError_(None)
        if exists:
            success, error = NSFileManager.defaultManager().removeItemAtURL_error_(panel.URL(), None)
            if not success:
                NSApp.presentError_(error)
                return
        
        self.buildProgressFilename.setStringValue_(os.path.basename(panel.URL().path()))
        self.startTaskInstall_(panel.URL().path())
    
    def startNextTask(self):
        if self.currentTask == IEDTaskInstall:
            self.startTaskImageScan()
        elif self.currentTask == IEDTaskImageScan:
            self.currentTask == IEDTaskNone
            self.progress = 100.0
            self.updateProgress()
            self.buildProgressBar.stopAnimation_(self)
            self.setUIEnabled_(True)
            self.progressWindow.orderOut_(self)
            self.mainWindow.makeKeyAndOrderFront_(self)
            alert = NSAlert.alloc().init()
            alert.setMessageText_(u"Build successful")
            alert.setInformativeText_(u"Built %s" % os.path.basename(self.destinationPath))
            alert.addButtonWithTitle_(u"OK")
            alert.addButtonWithTitle_(u"Reveal")
            button = alert.runModal()
            if button == NSAlertSecondButtonReturn:
                fileURL = NSURL.fileURLWithPath_(self.destinationPath)
                NSWorkspace.sharedWorkspace().activateFileViewerSelectingURLs_([fileURL])
        else:
            NSLog(u"No next task for task %d", self.currentTask)
    
    def getPackageSize_(self, path):
        p = subprocess.Popen([u"/usr/bin/du", u"-sk", path],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            NSLog(u"du failed with exit code %d", p.returncode)
        else:
            return int(out.split()[0]) * 1024
    
    def startTaskInstall_(self, destinationPath):
        self.destinationPath = destinationPath
        self.currentTask = IEDTaskInstall
        
        self.startTaskProgress()
        self.progressWindow.makeKeyAndOrderFront_(self)
        self.mainWindow.orderOut_(self)
        
        self.packagesToInstall = [{
            u"name": u"System",
            u"path": os.path.join(self.installerMountPoint, u"Packages/OSInstall.mpkg"),
            u"size": float(4 * 1024 * 1024 * 1024),
        }]
        for path in self.packageTableDataSource.packagePaths():
            self.buildProgressMessage.setStringValue_(u"Examining %s" % os.path.basename(path))
            self.packagesToInstall.append({
                u"name": os.path.basename(path),
                u"path": path,
                u"size": self.getPackageSize_(path),
            })
        if self.applyUpdatesCheckbox.state() == NSOnState:
            for update in self.updateTableDataSource.updates:
                self.packagesToInstall.append({
                    u"name": update[u"name"],
                    u"path": self.updateCache.getUpdatePath_(update[u"sha1"]),
                    u"size": update[u"size"],
                })
        self.totalPackagesSize = sum(pkg[u"size"] for pkg in self.packagesToInstall)
        
        args = [
            NSBundle.mainBundle().pathForResource_ofType_(u"progresswatcher", u"py"),
            u"--cd", NSBundle.mainBundle().resourcePath(),
            u"--socket", self.listenerPath,
            u"installesdtodmg",
            u"--user", NSUserName(),
            u"--group", grp.getgrgid(os.getgid()).gr_name,
            u"--output", self.destinationPath,
        ] + [pkg[u"path"] for pkg in self.packagesToInstall]
        NSLog(u"%@", args)
        self.performSelectorInBackground_withObject_(self.launchScript_, args)
    
    def launchScript_(self, args):
        shellscript = u' & " " & '.join(u"quoted form of arg%d" % i for i in range(len(args)))
        def escape(s):
            return s.replace(u"\\", u"\\\\").replace(u'"', u'\\"')
        applescript = u"\n".join([u'set arg%d to "%s"' % (i, escape(arg)) for i, arg in enumerate(args)] + \
                                 [u'do shell script %s with administrator privileges' % shellscript])
        trampoline = NSAppleScript.alloc().initWithSource_(applescript)
        evt, error = trampoline.executeAndReturnError_(None)
        if evt is None:
            NSLog(u"NSAppleScript failed with error: %@", error)
    
    def startTaskImageScan(self):
        self.currentTask = IEDTaskImageScan
        self.startTaskProgress()
        self.updateProgressMessage_(u"Scanning disk image for restore")
        args = [
            NSBundle.mainBundle().pathForResource_ofType_(u"progresswatcher", u"py"),
            u"--socket", self.listenerPath,
            u"imagescan",
            self.destinationPath,
        ]
        subprocess.Popen(args)



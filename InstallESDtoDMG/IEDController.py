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
from objc import IBAction, IBOutlet, nil

import os
import platform
from IEDSocketListener import *
from IEDDMGHelper import *


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
        self.dmgHelper = IEDDMGHelper.alloc().init()
        self.installerMountPoint = None
    
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
        panel.setNameFieldStringValue_(u"%s_%s_%s" % (u"baseos", self.installerVersion, self.installerBuild))
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        exists, error = panel.URL().checkResourceIsReachableAndReturnError_(None)
        if exists:
            success, error = NSFileManager.defaultManager().removeItemAtURL_error_(panel.URL(), None)
            if not success:
                NSApp.presentError_(error)
                return
        
        destinationPath = panel.URL().path()
        self.destinationLabel.setStringValue_(os.path.basename(destinationPath))
        
        self.startTaskProgress()
        args = [
            NSBundle.mainBundle().pathForResource_ofType_(u"progresswatcher", u"py"),
            u"--cd",
            NSBundle.mainBundle().resourcePath(),
            self.listenerPath,
            self.installerMountPoint,
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



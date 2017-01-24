# -*- coding: utf-8 -*-
#
#  IEDWorkflow.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-24.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
import os
import platform
import glob
import grp
import traceback
import time
import tempfile
import shutil
import datetime

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
from IEDUtil import *
from IEDSocketListener import *
from IEDDMGHelper import *
from IEDTemplate import *


class IEDWorkflow(NSObject):
    """The workflow contains the logic needed to setup, execute, and report
    the result of the build.
    """
    
    INSTALL_ESD = 1
    SYSTEM_IMAGE = 2
    
    def init(self):
        self = super(IEDWorkflow, self).init()
        if self is None:
            return None
        
        # Helper class for managing disk images.
        self.dmgHelper = IEDDMGHelper.alloc().initWithDelegate_(self)
        
        # Socket for communicating with helper processes.
        self.listener = IEDSocketListener.alloc().init()
        self.listenerPath = self.listener.listenOnSocket_withDelegate_("/tmp/se.gu.it.IEDSocketListener", self)
        
        # State for the workflow.
        self._source = None
        self._outputPath = None
        self._volumeName = "Macintosh HD"
        self.installerMountPoint = None
        self.additionalPackages = list()
        self.attachedPackageDMGs = dict()
        self.lastUpdateMessage = None
        self._authUsername = None
        self._authPassword = None
        self._volumeSize = None
        self._template = None
        self._finalizeAsrImagescan = True
        self.tempDir = None
        self.templatePath = None
        
        return self
    
    def initWithDelegate_(self, delegate):
        self = self.init()
        if self is None:
            return None
        
        self.delegate = delegate
        
        return self
    
    # Helper methods.
    
    def cleanup(self):
        LogDebug("cleanup")
        self.listener.stopListening()
        self.dmgHelper.detachAll_(None)
    
    def handleDetachResult_(self, result):
        if result["success"]:
            try:
                del self.attachedPackageDMGs[result["dmg-path"]]
            except KeyError:
                pass
        else:
            self.delegate.detachFailed_details_(result["dmg-path"], result["error-message"])
    
    def detachInstallerDMGs(self):
        LogDebug("Detaching installer DMGs")
        for dmgPath, mountPoint in self.attachedPackageDMGs.iteritems():
            self.dmgHelper.detach_selector_(dmgPath, self.handleDetachResult_)
    
    def alertFailedUnmounts_(self, failedUnmounts):
        if failedUnmounts:
            text = "\n".join("%s: %s" % (dmg, error) for dmg, error in failedUnmounts.iteritems())
            self.delegate.displayAlert_text_("Failed to eject dmgs", text)
    
    
    
    # External state of controller.
    
    def hasSource(self):
        return self.installerMountPoint is not None
    
    
    
    # Common delegate methods:
    #
    #     - (void)displayAlert:(NSString *)message text:(NSString *)text
    #     - (void)detachFailed:(NSString *)message details:(NSString *)details
    
    
    
    # Set a new installer source.
    #
    # Delegate methods:
    #
    #     - (void)ejectingSource
    #     - (void)examiningSource:(NSString *)path
    #     - (void)sourceSucceeded:(NSDictionary *)info
    #     - (void)sourceFailed:(NSString *)message text:(NSString *)text
    
    def setSource_(self, path):
        LogDebug("setSource:%@", path)
        
        self._source = None
        self.newSourcePath = path
        if self.installerMountPoint:
            self.delegate.ejectingSource()
            self.dmgHelper.detachAll_(self.continueSetSource_)
        else:
            self.continueSetSource_({})
    
    def source(self):
        return self._source
    
    def continueSetSource_(self, failedUnmounts):
        LogDebug("continueSetSource:%@", failedUnmounts)
        
        self.alertFailedUnmounts_(failedUnmounts)
        
        self.installESDPath = os.path.join(self.newSourcePath, "Contents/SharedSupport/InstallESD.dmg")
        if not os.path.exists(self.installESDPath):
            self.installESDPath = self.newSourcePath
        
        self.delegate.examiningSource_(self.newSourcePath)
        
        self.installerMountPoint = None
        self.baseSystemMountedFromPath = None
        self.dmgHelper.attach_selector_(self.installESDPath, self.handleSourceMountResult_)
    
    # handleSourceMountResult: may be called twice, once for InstallESD.dmg
    # and once for BaseSystem.dmg.
    def handleSourceMountResult_(self, result):
        LogDebug("handleSourceMountResult:%@", result)
        
        if not result["success"]:
            self.delegate.sourceFailed_text_("Failed to mount %s" % result["dmg-path"],
                                             result["error-message"])
            return
        
        mountPoint = result["mount-point"]
        
        # Update the icon if we find an installer app.
        for path in glob.glob(os.path.join(mountPoint, "Install*.app")):
            self.delegate.foundSourceForIcon_(path)
        
        # Don't set this again since 10.9 mounts BaseSystem.dmg after InstallESD.dmg.
        if self.installerMountPoint is None:
            self.installerMountPoint = mountPoint
            # Check if the source is an InstallESD or system image.
            if os.path.exists(os.path.join(mountPoint, "Packages", "OSInstall.mpkg")):
                self.sourceType = IEDWorkflow.INSTALL_ESD
                LogDebug("sourceType = INSTALL_ESD")
            else:
                self.sourceType = IEDWorkflow.SYSTEM_IMAGE
                LogDebug("sourceType = SYSTEM_IMAGE")
        
        baseSystemPath = os.path.join(mountPoint, "BaseSystem.dmg")
        
        # If we find a SystemVersion.plist we proceed to the next step.
        if os.path.exists(os.path.join(mountPoint, IEDUtil.VERSIONPLIST_PATH)):
            self.checkVersion_(mountPoint)
        # Otherwise check if there's a BaseSystem.dmg that we need to examine.
        elif os.path.exists(baseSystemPath):
            self.baseSystemMountedFromPath = baseSystemPath
            self.dmgHelper.attach_selector_(baseSystemPath, self.handleSourceMountResult_)
        else:
            self.delegate.sourceFailed_text_("Invalid source",
                                             "Couldn't find system version.")
    
    def checkVersion_(self, mountPoint):
        LogDebug("checkVersion:%@", mountPoint)
        
        # We're now examining InstallESD.dmg for 10.7/10.8, BaseSystem.dmg for
        # 10.9, or a system image.
        name, version, build = IEDUtil.readSystemVersion_(mountPoint)
        if self.baseSystemMountedFromPath:
            self.dmgHelper.detach_selector_(self.baseSystemMountedFromPath, self.handleDetachResult_)
        installerVersion = IEDUtil.splitVersion(version)
        runningVersion = IEDUtil.hostVersionTuple()
        LogNotice("Found source: %@ %@ %@", name, version, build)
        if installerVersion[:2] != runningVersion[:2]:
            self.delegate.ejectingSource()
            majorVersion = ".".join(str(x) for x in installerVersion[:2])
            self.delegate.sourceFailed_text_("OS version mismatch",
                                             "The major version of the installer and the current OS must match.\n\n" + \
                                             "%s %s %s installer requires running %s.x to build an image." % (
                                                name, version, build,
                                                majorVersion))
            self.dmgHelper.detachAll_(self.alertFailedUnmounts_)
            return
        LogNotice("Accepted source %@: %@ %@ %@", self.newSourcePath, name, version, build)
        self._source = self.newSourcePath
        self.installerName = name
        self.installerVersion = version
        self.installerBuild = build
        info = {
            "name": name,
            "version": version,
            "build": build,
            "template": self.loadImageTemplate_(mountPoint),
            "sourceType": self.sourceType,
        }
        self.delegate.sourceSucceeded_(info)
        # There's no reason to keep the dmg mounted if it's not an installer.
        if self.sourceType == IEDWorkflow.SYSTEM_IMAGE:
            self.dmgHelper.detachAll_(self.ejectSystemImage_)
    
    def loadImageTemplate_(self, mountPoint):
        LogDebug("checkTemplate:%@", mountPoint)
        try:
            path = glob.glob(os.path.join(mountPoint, "private/var/log/*.adtmpl"))[0]
        except IndexError:
            return None
        template = IEDTemplate.alloc().init()
        error = template.loadTemplateAndReturnError_(path)
        if error:
            LogWarning("Error reading %@ from image: %@", os.path.basename(path), error)
            return None
        return template
    
    def ejectSystemImage_(self, failedUnmounts):
        self.alertFailedUnmounts_(failedUnmounts)
    
    
    
    # Set a list of packages to install after the OS.
    
    def setPackagesToInstall_(self, packages):
        self.additionalPackages = packages
    
    # Path to generated disk image.
    
    def outputPath(self):
        return self._outputPath
    
    def setOutputPath_(self, path):
        self._outputPath = path
    
    # Volume name.
    
    def volumeName(self):
        return self._volumeName
    
    def setVolumeName_(self, name):
        self._volumeName = name
    
    # Username and password.
    
    def authUsername(self):
        return self._authUsername
    
    def setAuthUsername_(self, authUsername):
        self._authUsername = authUsername
    
    def authPassword(self):
        return self._authPassword
    
    def setAuthPassword_(self, authPassword):
        self._authPassword = authPassword
    
    # DMG size.
    
    def volumeSize(self):
        return self._volumeSize
    
    def setVolumeSize_(self, size):
        self._volumeSize = size
    
    # Finalize task: ASR imagescan.
    
    def finalizeAsrImagescan(self):
        return self._finalizeAsrImagescan
    
    def setFinalizeAsrImagescan_(self, finalizeAsrImagescan):
        self._finalizeAsrImagescan = finalizeAsrImagescan
    
    # Template to save in image.
    
    def template(self):
        return self._template
    
    def setTemplate_(self, template):
        self._template = template
    
    # Handle temporary directory during workflow.
    
    def createTempDir(self):
        self.tempDir = tempfile.mkdtemp()
    
    def deleteTempDir(self):
        if self.tempDir:
            try:
                shutil.rmtree(self.tempDir)
            except OSError as e:
                LogWarning("Can't remove temporary directory '%@': %@",
                           self.tempDir,
                           str(e))
            finally:
                self.tempDir = None
    
    # Start the workflow.
    #
    # Delegate methods:
    #
    #     - (void)buildStartingWithOutput:(NSString *)outputPath
    #     - (void)buildSetTotalWeight:(double)totalWeight
    #     - (void)buildSetPhase:(NSString *)phase
    #     - (void)buildSetProgress:(double)progress
    #     - (void)buildSetProgressMessage:(NSString *)message
    #     - (void)buildSucceeded
    #     - (void)buildFailed:(NSString *)message details:(NSString *)details
    #     - (void)buildStopped
    
    def start(self):
        LogNotice("Starting build")
        LogNotice("Using installer: %@ %@ %@", self.installerName, self.installerVersion, self.installerBuild)
        LogNotice("Using output path: %@", self.outputPath())
        LogNotice("TMPDIR is set to: %@", os.getenv("TMPDIR"))
        self.delegate.buildStartingWithOutput_(self.outputPath())
        
        self.createTempDir()
        LogDebug("Created temporary directory at %@", self.tempDir)
        
        if not self.template():
            self.fail_details_("Template missing",
                               "A template for inclusion in the image is required.")
            return
        
        datestamp = datetime.datetime.today().strftime("%Y%m%d")
        self.templatePath = os.path.join(self.tempDir, "AutoDMG-%s.adtmpl" % datestamp)
        LogDebug("Saving template to %@", self.templatePath)
        error = self.template().saveTemplateAndReturnError_(self.templatePath)
        if error:
            self.fail_details_("Couldn't save template to tempdir", error)
            return
        
        # The workflow is split into tasks, and each task has one or more
        # phases. Each phase of the installation is given a weight for the
        # progress bar, calculated from the size of the installer package.
        # Phases that don't install packages get an estimated weight.
        
        self.tasks = list()
        
        # Prepare for install.
        self.tasks.append({
            "title": "Prepare",
            "method": self.taskPrepare,
            "phases": [
                {"title": "Preparing", "weight": 34 * 1024 * 1024},
            ],
        })
        
        # Perform installation.
        installerPhases = [
            {"title": "Starting install",    "weight":       21 * 1024 * 1024},
            {"title": "Creating disk image", "weight":       21 * 1024 * 1024},
        ]
        if self.sourceType == IEDWorkflow.INSTALL_ESD:
            installerPhases.append({
                "title": "Installing OS",
                "weight": 4 * 1024 * 1024 * 1024,
            })
        for package in self.additionalPackages:
            installerPhases.append({
                "title": "Installing %s" % package.name(),
                # Add 100 MB to the weight to account for overhead.
                "weight": package.size() + 100 * 1024 * 1024,
            })
        installerPhases.extend([
            # hdiutil convert.
            {"title": "Converting disk image", "weight": 313 * 1024 * 1024},
        ])
        self.tasks.append({
            "title": "Install",
            "method": self.taskInstall,
            "phases": installerPhases,
        })

        # Finalize image. (Skip adding this task if Finalize: Scan for restore is unchecked.)
        if self._finalizeAsrImagescan:
            self.tasks.append({
                "title": "Finalize",
                "method": self.taskFinalize,
                "phases": [
                    {"title": "Scanning disk image", "weight":   2 * 1024 * 1024},
                    {"title": "Scanning disk image", "weight":   1 * 1024 * 1024},
                    {"title": "Scanning disk image", "weight": 150 * 1024 * 1024},
                    {"title": "Scanning disk image", "weight":  17 * 1024 * 1024, "optional": True},
                ],
            })
        
        # Finish build.
        self.tasks.append({
            "title": "Finish",
            "method": self.taskFinish,
            "phases": [
                {"title": "Finishing", "weight": 1 * 1024 * 1024},
            ],
        })
        
        # Calculate total weight of all phases.
        self.totalWeight = 0
        for task in self.tasks:
            LogInfo("Task %@ with %d phases:", task["method"].__name__, len(task["phases"]))
            for phase in task["phases"]:
                LogInfo("    Phase '%@' with weight %.1f", phase["title"], phase["weight"] / 1048576.0)
                self.totalWeight += phase["weight"]
        self.delegate.buildSetTotalWeight_(self.totalWeight)
        
        # Start the first task.
        self.progress = 0
        self.currentTask = None
        self.currentPhase = None
        self.nextTask()
    
    
    
    # Task and phase logic.
    
    def nextTask(self):
        LogDebug("nextTask, currentTask == %@", self.currentTask)
        
        if self.currentTask:
            if self.currentTask["phases"]:
                for phase in self.currentTask["phases"]:
                    if not phase.get("optional", False):
                        details = NSString.stringWithFormat_("Phases remaining: %@", self.currentTask["phases"])
                        self.fail_details_("Task finished prematurely", details)
                        return
        if self.tasks:
            self.currentTask = self.tasks.pop(0)
            LogNotice("Starting task %@ with %d phases", self.currentTask["title"], len(self.currentTask["phases"]))
            self.nextPhase()
            LogDebug("Calling %@()", self.currentTask["title"])
            self.currentTask["method"]()
            LogDebug("Returned from %@()", self.currentTask["title"])
        else:
            LogNotice("Build finished successfully, image saved to %@", self.outputPath())
            self.delegate.buildSucceeded()
            self.stop()
    
    def nextPhase(self):
        LogDebug("nextPhase, currentPhase == %@", self.currentPhase)
        
        if self.currentPhase:
            self.progress += self.currentPhase["weight"]
            LogInfo("Phase %@ with weight %ld finished after %.3f seconds",
                    self.currentPhase["title"],
                    self.currentPhase["weight"],
                    time.time() - self.phaseStartTime)
        self.phaseStartTime = time.time()
        try:
            self.currentPhase = self.currentTask["phases"].pop(0)
        except IndexError:
            self.fail_details_("No phase left in task", traceback.format_stack())
            return
        LogNotice("Starting phase: %@", self.currentPhase["title"])
        self.delegate.buildSetPhase_(self.currentPhase["title"])
        self.delegate.buildSetProgress_(self.progress)
    
    def fail_details_(self, message, text):
        LogError("Workflow failed: %@ (%@)", message, text)
        self.delegate.buildFailed_details_(message, text)
        self.stop()
    
    # Stop is called at the end of a workflow, regardless of if it succeeded
    # or failed.
    def stop(self):
        LogDebug("Workflow stopping")
        self.deleteTempDir()
        self.detachInstallerDMGs()
        self.delegate.buildStopped()
    
    
    
    # Task: Prepare.
    #
    #    1. Go through the list of packages to install and if they're
    #       contained in disk images, mount them.
    #    2. Generate a list of paths to the packages for the install task.
    
    def taskPrepare(self):
        LogDebug("taskPrepare")
        
        # Attach any disk images containing update packages.
        self.attachedPackageDMGs = dict()
        self.numberOfDMGsToAttach = 0
        for package in self.additionalPackages:
            if package.path().endswith(".dmg"):
                self.numberOfDMGsToAttach += 1
                LogInfo("Attaching %@", package.path())
                self.dmgHelper.attach_selector_(package.path(), self.attachPackageDMG_)
        if self.numberOfDMGsToAttach == 0:
            self.continuePrepare()
    
    # This will be called once for each disk image.
    def attachPackageDMG_(self, result):
        LogDebug("attachPackageDMG:%@", result)
        
        if not result["success"]:
            self.fail_details_("Failed to attach %s" % result["dmg-path"],
                               result["error-message"])
            return
        # Save result in a dictionary of dmg paths and their mount points.
        self.attachedPackageDMGs[result["dmg-path"]] = result["mount-point"]
        # If this was the last image we were waiting for, continue preparing
        # for install.
        if len(self.attachedPackageDMGs) == self.numberOfDMGsToAttach:
            self.continuePrepare()
    
    def continuePrepare(self):
        LogDebug("continuePrepare")
        
        # Generate a list of packages to install.
        self.packagesToInstall = list()
        if self.sourceType == IEDWorkflow.INSTALL_ESD:
            self.packagesToInstall.append(os.path.join(self.installerMountPoint,
                                                       "Packages",
                                                       "OSInstall.mpkg"))
        for package in self.additionalPackages:
            if package.path().endswith(".dmg"):
                mountPoint = self.attachedPackageDMGs[package.path()]
                LogDebug("Looking for packages and applications in %@: %@",
                         mountPoint,
                         glob.glob(os.path.join(mountPoint, "*")))
                packagePaths = glob.glob(os.path.join(mountPoint, "*.mpkg"))
                packagePaths += glob.glob(os.path.join(mountPoint, "*.pkg"))
                packagePaths += glob.glob(os.path.join(mountPoint, "*.app"))
                if len(packagePaths) == 0:
                    self.fail_details_("Nothing found to install",
                                       "No package or application found in %s" % package.name())
                    return
                elif len(packagePaths) > 1:
                    LogWarning("Multiple items found in %@, using %@", package.path(), packagePaths[0])
                self.packagesToInstall.append(packagePaths[0])
            else:
                self.packagesToInstall.append(package.path())
        if len(self.packagesToInstall) == 0:
            self.delegate.buildFailed_details_("Nothing to do",
                                               "There are no packages to install")
            self.stop()
            return
        
        # Calculate disk image size requirements.
        sizeRequirement = 0
        LogInfo("%d packages to install:", len(self.packagesToInstall))
        for path in self.packagesToInstall:
            LogInfo("    %@", path)
            installedSize = IEDUtil.getInstalledPkgSize_(path)
            if installedSize is None:
                self.delegate.buildFailed_details_("Failed to determine installed size",
                                                   "Unable to determine installation size requirements for %s" % path)
                self.stop()
                return
            sizeRequirement += installedSize
        sizeReqStr = IEDUtil.formatByteSize_(sizeRequirement)
        LogInfo("Workflow requires a %@ disk image", sizeReqStr)
        
        if self.volumeSize() is None:
            # Calculate DMG size. Multiply package requirements by 1.1, round
            # to the nearest GB, and add 23.
            self.setVolumeSize_(int((float(sizeRequirement) * 1.1) / (1000.0 * 1000.0 * 1000.0) + 23.5))
        else:
            # Make sure user specified image size is large enough.
            if sizeRequirement > self.volumeSize() * 1000 * 1000 * 1000:
                details = "Workflow requires %s and disk image is %d GB" % (sizeReqStr, self.volumeSize())
                self.delegate.buildFailed_details_("Disk image too small for workflow",
                                                   details)
                self.stop()
                return
        LogInfo("Using a %d GB disk image", self.volumeSize())
        
        # Task done.
        self.nextTask()
    
    
    
    # Task: Install.
    #
    #    1. Run the installesdtodmg.sh script with administrator privileges.
    #       Progress is sent back via notifications to the socket, which keeps
    #       the phases in sync with the script.
    
    def taskInstall(self):
        LogNotice("Install task running")
        
        # The script is wrapped with progresswatcher.py which parses script
        # output and sends it back as notifications to IEDSocketListener.
        args = [
            NSBundle.mainBundle().pathForResource_ofType_("progresswatcher", "py"),
            "--cd", NSBundle.mainBundle().resourcePath(),
            "--socket", self.listenerPath,
            "installesdtodmg",
            "--user", str(os.getuid()),
            "--group", str(os.getgid()),
            "--output", self.outputPath(),
            "--volume-name", self.volumeName(),
            "--size", str(self.volumeSize()),
            "--template", self.templatePath,
        ]
        if self.sourceType == IEDWorkflow.SYSTEM_IMAGE:
            args.extend(["--baseimage", self.source()])
        args.extend(self.packagesToInstall)
        LogInfo("Launching install with arguments:")
        for arg in args:
            LogInfo("    '%@'", arg)
        self.performSelectorInBackground_withObject_(self.launchScript_, args)
    
    def launchScript_(self, args):
        LogDebug("launchScript:")
        
        if (self.authPassword() is None) and (os.getuid() != 0):
            # Use GUI dialog to elevate privileges.
            task = STPrivilegedTask.alloc().init()
            task.setLaunchPath_(args[0])
            task.setArguments_(args[1:])
            status = task.launch()
            LogNotice("Install task launched with return code: %d", status)
            if status:
                self.performSelectorOnMainThread_withObject_waitUntilDone_(self.handleLaunchScriptError_, status, False)
        else:
            task = NSTask.alloc().init()
            if os.getuid() == 0:
                # No privilege elevation necessary.
                task.setLaunchPath_(args[0])
                task.setArguments_(args[1:])
            else:
                # Use sudo to elevate privileges.
                task.setLaunchPath_("/usr/bin/sudo")
                task.setArguments_(["-kSE"] + args)
                # Send password to sudo on stdin.
                passwordpipe = NSPipe.alloc().init()
                task.setStandardInput_(passwordpipe.fileHandleForReading())
                task.setStandardOutput_(NSFileHandle.fileHandleWithNullDevice())
                task.setStandardError_(NSFileHandle.fileHandleWithNullDevice())
                writer = passwordpipe.fileHandleForWriting()
                pwd = NSString.stringWithString_(self.authPassword() + "\n")
                writer.writeData_(pwd.dataUsingEncoding_(NSUTF8StringEncoding))
                writer.closeFile()
            try:
                task.launch()
                LogNotice("Install task launched%@", " with sudo" if os.getuid() != 0 else "")
            except BaseException as e:
                LogWarning("Install task launch failed with exception")
                self.performSelectorOnMainThread_withObject_waitUntilDone_(self.handleLaunchScriptError_, str(e), False)
                return
            task.waitUntilExit()
            LogNotice("Install task finished with exit status %d", task.terminationStatus())
            if task.terminationStatus() != 0:
                self.performSelectorOnMainThread_withObject_waitUntilDone_(self.handleLaunchScriptError_,
                                                                           "Install task failed with status %d" % task.terminationStatus(),
                                                                           False)
    
    def handleLaunchScriptError_(self, error):
        if isinstance(error, int):
            try:
                msg = {
                    -60001: "The authorization rights are invalid.",
                    -60002: "The authorization reference is invalid.",
                    -60003: "The authorization tag is invalid.",
                    -60004: "The returned authorization is invalid.",
                    -60005: "The authorization was denied.",
                    -60006: "The authorization was cancelled by the user.",
                    -60007: "The authorization was denied since no user interaction was possible.",
                    -60008: "Unable to obtain authorization for this operation.",
                    -60009: "The authorization is not allowed to be converted to an external format.",
                    -60010: "The authorization is not allowed to be created from an external format.",
                    -60011: "The provided option flag(s) are invalid for this authorization operation.",
                    -60031: "The specified program could not be executed.",
                    -60032: "An invalid status was returned during execution of a privileged tool.",
                    -60033: "The requested socket address is invalid (must be 0-1023 inclusive).",
                }[error]
            except KeyError:
                msg = "Unknown error (%d)." % error
        else:
            msg = error
        if error == -60006:
            LogDebug("User cancelled auth.")
            # User cancelled.
            self.stop()
        else:
            self.fail_details_("Build failed", msg)
    
    
    
    # Task: Finalize.
    #
    #    1. Scan the image for restore.
    
    def taskFinalize(self):
        LogNotice("Finalize task running")
        
        self.delegate.buildSetProgressMessage_("Scanning disk image for restore")
        # The script is wrapped with progresswatcher.py which parses script
        # output and sends it back as notifications to IEDSocketListener.
        args = [
            NSBundle.mainBundle().pathForResource_ofType_("progresswatcher", "py"),
            "--socket", self.listenerPath,
            "imagescan",
            self.outputPath(),
        ]
        LogInfo("Launching finalize with arguments:")
        for arg in args:
            LogInfo("    '%@'", arg)
        self.performSelectorInBackground_withObject_(self.launchFinalize_, args)
    
    def launchFinalize_(self, args):
        try:
            task = NSTask.alloc().init()
            task.setLaunchPath_(args[0])
            task.setArguments_(args[1:])
            task.launch()
            task.waitUntilExit()
            if task.terminationStatus() == 0:
                LogDebug("Finalize exited with status %d", task.terminationStatus())
            else:
                errMsg = "Finalize task failed with status %d" % task.terminationStatus()
                self.performSelectorOnMainThread_withObject_waitUntilDone_(self.handleFinalizeError_,
                                                                           errMsg,
                                                                           False)
        except BaseException as e:
            errMsg = "Failed to launch finalize task: %s" % str(e)
            self.performSelectorOnMainThread_withObject_waitUntilDone_(self.handleFinalizeError_,
                                                                       errMsg,
                                                                       False)
    
    def handleFinalizeError_(self, errMsg):
        LogError("Finalize failed: %@", errMsg)
        self.fail_details_("Finalize failed", errMsg)
    
    
    
    # Task: Finish
    #
    #    1. Just a dummy task to keep the progress bar from finishing
    #       prematurely.
    
    def taskFinish(self):
        LogNotice("Finish")
        self.delegate.buildSetProgress_(self.totalWeight)
        self.nextTask()
    
    # SocketListener delegate methods.
    
    def socketReceivedMessage_(self, msg):
        # The message is a dictionary with "action" as the only required key.
        action = msg["action"]
        
        if action == "update_progress":
            percent = msg["percent"]
            currentProgress = self.progress + self.currentPhase["weight"] * percent / 100.0
            self.delegate.buildSetProgress_(currentProgress)
        
        elif action == "update_message":
            if self.lastUpdateMessage != msg["message"]:
                # Only log update messages when they change.
                LogInfo("%@", msg["message"])
            self.lastUpdateMessage = msg["message"]
            self.delegate.buildSetProgressMessage_(msg["message"])
        
        elif action == "select_phase":
            LogNotice("Script phase: %@", msg["phase"])
            self.nextPhase()
        
        elif action == "log_message":
            LogMessage(msg["log_level"], msg["message"])
        
        elif action == "notify_failure":
            self.fail_details_("Build failed", msg["message"])
        
        elif action == "notify_success":
            LogNotice("Build success: %@", msg["message"])
        
        elif action == "task_done":
            status = msg["termination_status"]
            if status == 0:
                self.nextTask()
            else:
                details = NSString.stringWithFormat_("Task exited with status %@", msg["termination_status"])
                LogError("%@", details)
                # Status codes 100-199 are from installesdtodmg.sh, and have
                # been preceeded by a "notify_failure" message.
                if (status < 100) or (status > 199):
                    self.fail_details_("Build failed", details)
        
        else:
            self.fail_details_("Unknown progress notification", "Message: %@", msg)

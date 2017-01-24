# -*- coding: utf-8 -*-
#
#  IEDCLIController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2014-01-28.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
from AppKit import *
from Collaboration import CBIdentity, CBIdentityAuthority

import os
import sys
import getpass
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
from IEDUpdateCache import *
from IEDProfileController import *
from IEDWorkflow import *
from IEDTemplate import *
from IEDUtil import *


class IEDCLIController(NSObject):
    """Main controller class for CLI interface.
    
    Methods starting with cmd are exposed as verbs to the CLI. A method named
    cmdVerb_() should have a corresponding addargsVerb_() that takes an
    argparser subparser object as its argument, which should be populated."""
    
    def init(self):
        self = super(IEDCLIController, self).init()
        if self is None:
            return None
        
        self.cache = IEDUpdateCache.alloc().initWithDelegate_(self)
        self.workflow = IEDWorkflow.alloc().initWithDelegate_(self)
        self.profileController = IEDProfileController.alloc().init()
        self.profileController.awakeFromNib()
        self.profileController.setDelegate_(self)
        self.cache.pruneAndCreateSymlinks(self.profileController.updatePaths)
        
        self.busy = False
        
        self.progressMax = 1.0
        self.lastMessage = ""
        
        self.hasFailed = False
        
        return self
    
    def listVerbs(self):
        return list(item[3:].rstrip("_").lower() for item in dir(self) if item.startswith("cmd"))
    
    def cleanup(self):
        self.workflow.cleanup()
    
    def waitBusy(self):
        runLoop = NSRunLoop.currentRunLoop()
        while self.busy:
            nextfire = runLoop.limitDateForMode_(NSDefaultRunLoopMode)
            if not self.busy:
                break
            if not runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, nextfire):
                self.failWithMessage_("runMode:beforeDate: failed")
                break
    
    def failWithMessage_(self, message):
        LogError("%@", message)
        self.hasFailed = True
        self.busy = False
    
    
    # Build image.
    
    def cmdBuild_(self, args):
        """Build image"""
        
        # Parse arguments.
        
        sourcePath = IEDUtil.installESDPath_(args.source) or \
                        IEDUtil.systemImagePath_(args.source)
        if sourcePath:
            templatePath = None
        else:
            templatePath = self.checkTemplate_(args.source)
        
        if not sourcePath and not templatePath:
            self.failWithMessage_("'%s' is not a valid OS X installer, OS X system image or AutoDMG template" % args.source)
            return os.EX_DATAERR
        
        if templatePath:
            template = IEDTemplate.alloc().init()
            error = template.loadTemplateAndReturnError_(templatePath)
            if error:
                self.failWithMessage_("Couldn't load template from '%s': %s" % (templatePath, error))
                return os.EX_DATAERR
        else:
            template = IEDTemplate.alloc().initWithSourcePath_(sourcePath)
        
        if args.installer:
            template.setSourcePath_(args.installer)
        if args.output:
            template.setOutputPath_(args.output)
        if args.name:
            template.setVolumeName_(args.name)
        if args.size:
            template.setVolumeSize_(args.size)
        if args.skip_asr_imagescan:
            template.setFinalizeAsrImagescan_(False)
        if args.updates is not None:
            template.setApplyUpdates_(True)
        if args.packages:
            if not template.setAdditionalPackages_(args.packages):
                self.failWithMessage_("Additional packages failed verification: %s" % template.additionalPackageError)
                return os.EX_DATAERR
        
        if not template.sourcePath:
            self.failWithMessage_("No source path")
            return os.EX_USAGE
        if not template.outputPath:
            self.failWithMessage_("No output path")
            return os.EX_USAGE
        
        LogNotice("Installer: %@", template.sourcePath)
        
        # Set the source.
        self.busy = True
        self.workflow.setSource_(template.sourcePath)
        self.waitBusy()
        if self.hasFailed:
            return os.EX_DATAERR
        
        template.resolveVariables_({
            "OSNAME":      self.installerName,
            "OSVERSION":   self.installerVersion,
            "OSBUILD":     self.installerBuild,
        })
        
        LogNotice("Output Path: %@", template.outputPath)
        LogNotice("Volume Name: %@", template.volumeName)
        
        # Generate the list of updates to install.
        updates = list()
        if template.applyUpdates:
            profile = self.profileController.profileForVersion_Build_(self.installerVersion, self.installerBuild)
            if profile is None:
                self.failWithMessage_(self.profileController.whyNoProfileForVersion_build_(self.installerVersion,
                                                                                           self.installerBuild))
                return os.EX_DATAERR
            
            missingUpdates = list()
            
            for update in profile:
                LogNotice("Update: %@ (%@)", update["name"], IEDUtil.formatByteSize_(update["size"]))
                package = IEDPackage.alloc().init()
                package.setName_(update["name"])
                package.setPath_(self.cache.updatePath_(update["sha1"]))
                package.setSize_(update["size"])
                package.setUrl_(update["url"])
                package.setSha1_(update["sha1"])
                if not self.cache.isCached_(update["sha1"]):
                    if args.download_updates:
                        missingUpdates.append(package)
                    else:
                        self.failWithMessage_("Can't apply updates, %s is missing from cache" % update["name"])
                        return os.EX_DATAERR
                updates.append(package)
            
            if missingUpdates:
                self.cache.downloadUpdates_(missingUpdates)
                self.busy = True
                self.waitBusy()
                if self.hasFailed:
                    self.failWithMessage_("Can't build due to updates missing from cache")
                    return 1    # EXIT_FAILURE
                updates.extend(missingUpdates)
                LogNotice("All updates for %@ %@ downloaded", self.installerVersion, self.installerBuild)
        
        # Generate the list of additional packages to install.
        template.resolvePackages()
        for package in template.packagesToInstall:
            LogNotice("Package: %@ (%@)", package.name(), IEDUtil.formatByteSize_(package.size()))
        
        # Check the output path.
        if os.path.exists(template.outputPath):
            if args.force:
                try:
                    os.unlink(template.outputPath)
                except OSError as e:
                    self.failWithMessage_("Couldn't remove %s: %s" % (template.outputPath, str(e)))
                    return os.EX_CANTCREAT
            else:
                self.failWithMessage_("%s already exists" % template.outputPath)
                return os.EX_CANTCREAT
        else:
            outputDir = os.path.dirname(template.outputPath)
            if outputDir and not os.path.exists(outputDir):
                try:
                    os.makedirs(outputDir)
                except OSError as e:
                    self.failWithMessage_("%s does not exist and can't be created: %s" % (outputDir, str(e)))
                    return os.EX_CANTCREAT
        
        # If we're not running as root get the password for authentication.
        if os.getuid() != 0:
            username = NSUserName()
            currentUser = CBIdentity.identityWithName_authority_(username, CBIdentityAuthority.defaultIdentityAuthority())
            passwordOK = False
            while not passwordOK:
                password = getpass.getpass("Password for %s: " % username).decode("utf-8")
                if currentUser.authenticateWithPassword_(password):
                    passwordOK = True
            self.workflow.setAuthUsername_(username)
            self.workflow.setAuthPassword_(password)
        
        # Start the workflow.
        self.busy = True
        self.workflow.setPackagesToInstall_(updates + template.packagesToInstall)
        self.workflow.setOutputPath_(template.outputPath)
        self.workflow.setVolumeName_(template.volumeName)
        self.workflow.setVolumeSize_(template.volumeSize)
        self.workflow.setFinalizeAsrImagescan_(template.finalizeAsrImagescan)
        self.workflow.setTemplate_(template)
        self.workflow.start()
        self.waitBusy()
        if self.hasFailed:
            return 1    # EXIT_FAILURE
        
        return os.EX_OK
    
    def checkTemplate_(self, path):
        path = IEDUtil.resolvePath_(path)
        if not path:
            return None
        if not os.path.exists(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".plist", ".adtmpl"):
            return None
        return path
    
    def addargsBuild_(self, argparser):
        argparser.add_argument("source", help="OS X installer, OS X system image or AutoDMG template")
        argparser.add_argument("-o", "--output", help="DMG output path")
        argparser.add_argument("-i", "--installer", help="Override installer in template")
        argparser.add_argument("-n", "--name", help="Installed system volume name")
        argparser.add_argument("-s", "--size", type=int, help="Installed system volume size, in GB")
        argparser.add_argument("--skip-asr-imagescan", action="store_true", help="Skip `asr imagescan` (Scan for Restore) phase")
        argparser.add_argument("-u", "--updates", action="store_const", const=True, help="Apply updates")
        argparser.add_argument("-U", "--download-updates", action="store_true", help="Download missing updates")
        argparser.add_argument("-f", "--force", action="store_true", help="Overwrite output")
        argparser.add_argument("packages", nargs="*", help="Additional packages")
    
    
    
    # List updates.
    
    def cmdList_(self, args):
        """List updates"""
        
        profile = self.profileController.profileForVersion_Build_(args.version, args.build)
        if profile is None:
            self.failWithMessage_(self.profileController.whyNoProfileForVersion_build_(args.version, args.build))
            return os.EX_DATAERR
        
        LogNotice("%d update%@ for %@ %@:", len(profile), "" if len(profile) == 1 else "s", args.version, args.build)
        for update in profile:
            LogNotice("    %@%@ (%@)",
                      "[cached] " if self.cache.isCached_(update["sha1"]) else "",
                      update["name"],
                      IEDUtil.formatByteSize_(update["size"]))
        
        return os.EX_OK
    
    def addargsList_(self, argparser):
        argparser.add_argument("version", help="OS X version")
        argparser.add_argument("build", help="OS X build")
    
    
    
    # Download updates.
    
    def cmdDownload_(self, args):
        """Download updates"""
        
        profile = self.profileController.profileForVersion_Build_(args.version, args.build)
        if profile is None:
            self.failWithMessage_(self.profileController.whyNoProfileForVersion_build_(args.version, args.build))
            return os.EX_DATAERR
        
        updates = list()
        for update in profile:
            if not self.cache.isCached_(update["sha1"]):
                package = IEDPackage.alloc().init()
                package.setName_(update["name"])
                package.setPath_(self.cache.updatePath_(update["sha1"]))
                package.setSize_(update["size"])
                package.setUrl_(update["url"])
                package.setSha1_(update["sha1"])
                updates.append(package)
        
        if updates:
            self.cache.downloadUpdates_(updates)
            self.busy = True
            self.waitBusy()
        
        if self.hasFailed:
            return 1    # EXIT_FAILURE
        
        LogNotice("All updates for %@ %@ downloaded", args.version, args.build)
        
        return os.EX_OK
    
    def addargsDownload_(self, argparser):
        argparser.add_argument("version", help="OS X version")
        argparser.add_argument("build", help="OS X build")
    
    
    
    # Update profiles.
    
    def cmdUpdate_(self, args):
        """Update profiles"""
        
        self.profileController.updateFromURL_(args.url)
        self.busy = True
        self.waitBusy()
        
        if self.hasFailed:
            return 1    # EXIT_FAILURE
        
        return os.EX_OK
    
    def addargsUpdate_(self, argparser):
        defaults = NSUserDefaults.standardUserDefaults()
        url = NSURL.URLWithString_(defaults.stringForKey_("UpdateProfilesURL"))
        argparser.add_argument("-u", "--url", default=url, help="Profile URL")
    
    
    
    # Workflow delegate methods.
    
    def detachFailed_details_(self, dmgPath, details):
        LogError("Failed to detach '%@': %@", dmgPath, details)
    
    def ejectingSource(self):
        LogInfo("%@", "Ejecting source…")
    
    def examiningSource_(self, path):
        LogInfo("%@", "Examining source…")
    
    def foundSourceForIcon_(self, path):
        pass
    
    def sourceSucceeded_(self, info):
        self.installerName = info["name"]
        self.installerVersion = info["version"]
        self.installerBuild = info["build"]
        LogNotice("Found installer: %@ %@ %@", info["name"], info["version"], info["build"])
        self.busy = False
    
    def sourceFailed_text_(self, message, text):
        self.failWithMessage_("Source failed: %s" % message)
        self.failWithMessage_("    %s" % text)
    
    
    
    def buildStartingWithOutput_(self, outputPath):
        self.busy = True
        self.lastProgressPercent = -100.0
    
    def buildSetTotalWeight_(self, totalWeight):
        self.progressMax = totalWeight
    
    def buildSetPhase_(self, phase):
        LogNotice("phase: %@", phase)
    
    def buildSetProgress_(self, progress):
        percent = 100.0 * progress / self.progressMax
        if abs(percent - self.lastProgressPercent) >= 0.1:
            LogInfo("progress: %.1f%%", percent)
            self.lastProgressPercent = percent
    
    def buildSetProgressMessage_(self, message):
        if message != self.lastMessage:
            LogInfo("message: %@", message)
            self.lastMessage = message
    
    def buildSucceeded(self):
        LogNotice("Build successful")
    
    def buildFailed_details_(self, message, details):
        self.failWithMessage_("Build failed: %s" % message)
        self.failWithMessage_("    %s" % details)
    
    def buildStopped(self):
        self.busy = False
    
    
    
    # UpdateCache delegate methods.
    
    def downloadAllDone(self):
        LogDebug("downloadAllDone")
        self.busy = False
    
    def downloadStarting_(self, package):
        LogNotice("Downloading %@ (%@)", package.name(), IEDUtil.formatByteSize_(package.size()))
        self.lastProgressPercent = -100.0
        self.lastProgressTimestamp = NSDate.alloc().init()
    
    def downloadStarted_(self, package):
        LogDebug("downloadStarted:")
    
    def downloadStopped_(self, package):
        LogDebug("downloadStopped:")
    
    def downloadGotData_bytesRead_(self, package, bytes):
        percent = 100.0 * float(bytes) / float(package.size())
        # Log progress if we've downloaded more than 10%, more than one second
        # has passed, or if we're at 100%.
        if (abs(percent - self.lastProgressPercent) >= 10.0) or \
           (abs(self.lastProgressTimestamp.timeIntervalSinceNow()) >= 1.0) or \
           (bytes == package.size()):
            LogInfo("progress: %.1f%%", percent)
            self.lastProgressPercent = percent
            self.lastProgressTimestamp = NSDate.alloc().init()
    
    def downloadSucceeded_(self, package):
        LogDebug("downloadSucceeded:")
    
    def downloadFailed_withError_(self, package, message):
        self.failWithMessage_("Download of %s failed: %s" % (package.name(), message))
    
    
    
    # IEDProfileController delegate methods.
    
    def profileUpdateAllDone(self):
        self.busy = False
    
    def profileUpdateFailed_(self, error):
        self.failWithMessage_("%@", error.localizedDescription())
    
    def profileUpdateSucceeded_(self, publicationDate):
        LogDebug("profileUpdateSucceeded:%@", publicationDate)
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setObject_forKey_(NSDate.date(), "LastUpdateProfileCheck")
    
    def profilesUpdated(self):
        LogDebug("profilesUpdated")
        self.cache.pruneAndCreateSymlinks(self.profileController.updatePaths)

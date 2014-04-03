#-*- coding: utf-8 -*-
#
#  IEDCLIController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2014-01-28.
#  Copyright 2013-2014 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
from AppKit import *

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
        self.lastMessage = u""
        
        self.hasFailed = False
        
        return self
    
    def listVerbs(self):
        return list(item[3:].rstrip(u"_").lower() for item in dir(self) if item.startswith(u"cmd"))
    
    def cleanup(self):
        self.workflow.cleanup()
    
    def waitBusy(self):
        runLoop = NSRunLoop.currentRunLoop()
        while self.busy:
            nextfire = runLoop.limitDateForMode_(NSDefaultRunLoopMode)
            if not self.busy:
                break
            if not runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, nextfire):
                self.failWithMessage_(u"runMode:beforeDate: failed")
                break
    
    def failWithMessage_(self, message):
        LogError(u"%@", message)
        self.hasFailed = True
        self.busy = False
    
    
    # Build image.
    
    def cmdBuild_(self, args):
        """Build image"""
        
        # Parse arguments.
        
        sourcePath = IEDUtil.installESDPath_(args.source)
        if sourcePath:
            templatePath = None
        else:
            templatePath = self.checkTemplate_(args.source)
        
        if not sourcePath and not templatePath:
            self.failWithMessage_(u"'%s' is not a valid OS X installer or AutoDMG template" % args.source)
            return os.EX_DATAERR
        
        if templatePath:
            template = IEDTemplate.alloc().init()
            error = template.loadTemplateAndReturnError_(templatePath)
            if error:
                self.failWithMessage_(u"Couldn't load template from '%s': %s" % (templatePath, error))
                return os.EX_DATAERR
        else:
            template = IEDTemplate.alloc().initWithSourcePath_(sourcePath)
        
        if args.installer:
            template.setSourcePath_(args.installer)
        if args.output:
            template.setOutputPath_(args.output)
        if args.name:
            template.setVolumeName_(args.name)
        if args.updates is not None:
            template.setApplyUpdates_(True)
        if args.packages:
            if not template.setAdditionalPackages_(args.packages):
                self.failWithMessage_(u"Additional packages failed verification")
                return os.EX_DATAERR
        
        if not template.sourcePath:
            self.failWithMessage_(u"No source path")
            return os.EX_USAGE
        if not template.outputPath:
            self.failWithMessage_(u"No output path")
            return os.EX_USAGE
        
        LogNotice(u"Installer: %@", template.sourcePath)
        LogNotice(u"Output Path: %@", template.outputPath)
        LogNotice(u"Volume Name: %@", template.volumeName)
        
        # Set the source.
        self.busy = True
        self.workflow.setSource_(template.sourcePath)
        self.waitBusy()
        if self.hasFailed:
            return os.EX_DATAERR
        
        # Generate the list of updates to install.
        updates = list()
        if template.applyUpdates:
            profile = self.profileController.profileForVersion_Build_(self.installerVersion, self.installerBuild)
            if profile is None:
                self.failWithMessage_(self.profileController.whyNoProfileForVersion_build_(self.installerVersion,
                                                                                           self.installerBuild))
                return os.EX_DATAERR
            
            for update in profile:
                LogNotice(u"Update: %@ (%@)", update[u"name"], IEDUtil.formatBytes_(update[u"size"]))
                if not self.cache.isCached_(update[u"sha1"]):
                    self.failWithMessage_(u"Can't apply updates, %s is missing from cache" % update[u"name"])
                    return os.EX_DATAERR
                package = IEDPackage.alloc().init()
                package.setName_(update[u"name"])
                package.setPath_(self.cache.updatePath_(update[u"sha1"]))
                package.setSize_(update[u"size"])
                package.setUrl_(update[u"url"])
                package.setSha1_(update[u"sha1"])
                updates.append(package)
        
        # Generate the list of additional packages to install.
        template.resolvePackages()
        for package in template.packagesToInstall:
            LogNotice(u"Package: %@ (%@)", package.name(), IEDUtil.formatBytes_(package.size()))
        
        # Check the output path.
        if os.path.exists(template.outputPath):
            if args.force:
                try:
                    os.unlink(template.outputPath)
                except OSError as e:
                    self.failWithMessage_(u"Couldn't remove %s: %s" % (template.outputPath, unicode(e)))
                    return os.EX_CANTCREAT
            else:
                self.failWithMessage_(u"%s already exists" % template.outputPath)
                return os.EX_CANTCREAT
        else:
            outputDir = os.path.dirname(template.outputPath)
            if outputDir and not os.path.exists(outputDir):
                try:
                    os.makedirs(outputDir)
                except OSError as e:
                    self.failWithMessage_(u"%s does not exist and can't be created: %s" % (outputDir, unicode(e)))
                    return os.EX_CANTCREAT
        
        # If we're not running as root get the password for authentication.
        if os.getuid() != 0:
            username = getpass.getuser()
            password = getpass.getpass(u"Password for %s: " % username)
            self.workflow.setAuthUsername_(username)
            self.workflow.setAuthPassword_(password)
        
        # Start the workflow.
        self.busy = True
        self.workflow.setPackagesToInstall_(updates + template.packagesToInstall)
        self.workflow.setOutputPath_(template.outputPath)
        self.workflow.setVolumeName_(template.volumeName)
        self.workflow.setVolumeSize_(template.volumeSize)
        self.workflow.start()
        self.waitBusy()
        if self.hasFailed:
            return 1 # EXIT_FAILURE
        
        return os.EX_OK
    
    def checkTemplate_(self, path):
        path = IEDUtil.resolvePath_(path)
        if not path:
            return None
        if not os.path.exists(path):
            return None
        ext = os.path.splitext(path)[1].lower()
        if ext not in (u".plist", u".adtmpl"):
            return None
        return path
    
    def addargsBuild_(self, argparser):
        argparser.add_argument(u"source", help=u"OS X installer or AutoDMG template")
        argparser.add_argument(u"-o", u"--output", help=u"DMG output path")
        argparser.add_argument(u"-i", u"--installer", help=u"Override installer in template")
        argparser.add_argument(u"-n", u"--name", help=u"Installed system volume name")
        argparser.add_argument(u"-u", u"--updates", action=u"store_const", const=True, help=u"Apply updates")
        argparser.add_argument(u"-f", u"--force", action=u"store_true", help=u"Overwrite output")
        argparser.add_argument(u"packages", nargs=u"*", help=u"Additional packages")
    
    
    
    # List updates.
    
    def cmdList_(self, args):
        """List updates"""
        
        profile = self.profileController.profileForVersion_Build_(args.version, args.build)
        if profile is None:
            self.failWithMessage_(self.profileController.whyNoProfileForVersion_build_(args.version, args.build))
            return os.EX_DATAERR
        
        LogNotice(u"%d update%@ for %@ %@:", len(profile), u"" if len(profile) == 1 else u"s", args.version, args.build)
        for update in profile:
            LogNotice(u"    %@%@ (%@)",
                      u"[cached] " if self.cache.isCached_(update[u"sha1"]) else u"",
                      update[u"name"],
                      IEDUtil.formatBytes_(update[u"size"]))
        
        return os.EX_OK
    
    def addargsList_(self, argparser):
        argparser.add_argument(u"version", help=u"OS X version")
        argparser.add_argument(u"build", help=u"OS X build")
    
    
    
    # Download updates.
    
    def cmdDownload_(self, args):
        """Download updates"""
        
        profile = self.profileController.profileForVersion_Build_(args.version, args.build)
        if profile is None:
            self.failWithMessage_(self.profileController.whyNoProfileForVersion_build_(args.version, args.build))
            return os.EX_DATAERR
        
        updates = list()
        for update in profile:
            if not self.cache.isCached_(update[u"sha1"]):
                package = IEDPackage.alloc().init()
                package.setName_(update[u"name"])
                package.setPath_(self.cache.updatePath_(update[u"sha1"]))
                package.setSize_(update[u"size"])
                package.setUrl_(update[u"url"])
                package.setSha1_(update[u"sha1"])
                updates.append(package)
        
        if updates:
            self.cache.downloadUpdates_(updates)
            self.busy = True
            self.waitBusy()
        
        if self.hasFailed:
            return 1 # EXIT_FAILURE
        
        LogNotice(u"All updates for %@ %@ downloaded", args.version, args.build)
        
        return os.EX_OK
    
    def addargsDownload_(self, argparser):
        argparser.add_argument(u"version", help=u"OS X version")
        argparser.add_argument(u"build", help=u"OS X build")
    
    
    
    # Update profiles.
    
    def cmdUpdate_(self, args):
        """Update profiles"""
        
        self.profileController.updateFromURL_(args.url)
        self.busy = True
        self.waitBusy()
        
        if self.hasFailed:
            return 1 # EXIT_FAILURE
        
        return os.EX_OK
    
    def addargsUpdate_(self, argparser):
        defaults = NSUserDefaults.standardUserDefaults()
        url = NSURL.URLWithString_(defaults.stringForKey_(u"UpdateProfilesURL"))
        argparser.add_argument(u"-u", u"--url", default=url, help=u"Profile URL")
    
    
    
    # Workflow delegate methods.
    
    def ejectingSource(self):
        LogInfo("%@", u"Ejecting source…")
    
    def examiningSource_(self, path):
        LogInfo("%@", u"Examining source…")
    
    def foundSourceForIcon_(self, path):
        pass
    
    def sourceSucceeded_(self, info):
        self.installerName = info[u"name"]
        self.installerVersion = info[u"version"]
        self.installerBuild = info[u"build"]
        LogNotice(u"Found installer: %s %s %s" % (info[u"name"], info[u"version"], info[u"build"]))
        #self.updateController.loadProfileForVersion_build_(info[u"version"], info[u"build"])
        self.busy = False
    
    def sourceFailed_text_(self, message, text):
        self.failWithMessage_(u"Source failed: %s" % message)
        self.failWithMessage_(u"    %s" % text)
    
    
    
    def buildStartingWithOutput_(self, outputPath):
        self.busy = True
        self.lastProgressPercent = -100.0
    
    def buildSetTotalWeight_(self, totalWeight):
        self.progressMax = totalWeight
    
    def buildSetPhase_(self, phase):
        LogNotice(u"phase: %@", phase)
    
    def buildSetProgress_(self, progress):
        percent = 100.0 * progress / self.progressMax
        if abs(percent - self.lastProgressPercent) >= 0.1:
            LogInfo(u"progress: %.1f%%", percent)
            self.lastProgressPercent = percent
    
    def buildSetProgressMessage_(self, message):
        if message != self.lastMessage:
            LogInfo(u"message: %@", message)
            self.lastMessage = message
    
    def buildSucceeded(self):
        LogNotice(u"Build successful")
    
    def buildFailed_details_(self, message, details):
        self.failWithMessage_(u"Build failed: %s" % message)
        self.failWithMessage_(u"    %s" % details)
    
    def buildStopped(self):
        self.busy = False
    
    
    
    # UpdateCache delegate methods.
    
    def downloadAllDone(self):
        LogDebug(u"downloadAllDone")
        self.busy = False
    
    def downloadStarting_(self, package):
        LogNotice(u"Downloading %@ (%@)", package.name(), IEDUtil.formatBytes_(package.size()))
        self.lastProgressPercent = -100.0
        self.lastProgressTimestamp = NSDate.alloc().init()
    
    def downloadStarted_(self, package):
        LogDebug(u"downloadStarted:")
    
    def downloadStopped_(self, package):
        LogDebug(u"downloadStopped:")
    
    def downloadGotData_bytesRead_(self, package, bytes):
        percent = 100.0 * float(bytes) / float(package.size())
        # Log progress if we've downloaded more than 10%, more than one second
        # has passed, or if we're at 100%.
        if (abs(percent - self.lastProgressPercent) >= 10.0) or \
           (abs(self.lastProgressTimestamp.timeIntervalSinceNow()) >= 1.0) or \
           (bytes == package.size()):
            LogInfo(u"progress: %.1f%%", percent)
            self.lastProgressPercent = percent
            self.lastProgressTimestamp = NSDate.alloc().init()
    
    def downloadSucceeded_(self, package):
        LogDebug(u"downloadSucceeded:")
    
    def downloadFailed_withError_(self, package, message):
        self.failWithMessage_(u"Download of %s failed: %s" % (package.name(), message))
    
    
    
    # IEDProfileController delegate methods.
    
    def profileUpdateAllDone(self):
        self.busy = False
    
    def profileUpdateFailed_(self, error):
        self.failWithMessage_(u"%@", error.localizedDescription())
    
    def profileUpdateSucceeded_(self, publicationDate):
        LogDebug(u"profileUpdateSucceeded:%@", publicationDate)
        defaults = NSUserDefaults.standardUserDefaults()
        defaults.setObject_forKey_(NSDate.date(), u"LastUpdateProfileCheck")
    
    def profilesUpdated(self):
        LogDebug(u"profilesUpdated")
        self.cache.pruneAndCreateSymlinks(self.profileController.updatePaths)

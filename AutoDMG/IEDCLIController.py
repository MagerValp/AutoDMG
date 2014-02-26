#-*- coding: utf-8 -*-
#
#  IEDCLIController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2014-01-28.
#  Copyright (c) 2014 University of Gothenburg. All rights reserved.
#

from Foundation import *
from AppKit import *

import sys
import os.path
from IEDLog import *
from IEDUpdateCache import *
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
        self.busy = False
        
        self.progressMax = 1.0
        self.lastProgress = -1.0
        self.lastMessage = u""
        
        self.hasFailed = False
        
        return self
    
    def listVerbs(self):
        return list(item[3:].rstrip(u"_").lower() for item in dir(self) if item.startswith(u"cmd"))
    
    def cleanup(self):
        self.workflow.cleanup()
    
    def failWithMessage_(self, message):
        LogError(u"%@", message)
        print >>sys.stderr, message.encode(u"utf-8")
        self.hasFailed = True
        self.busy = False
    
    
    # Build image.
    
    def cmdBuild_(self, args):
        """Build image"""
        
        sourcePath = IEDUtil.installESDPath_(args.source)
        if sourcePath:
            templatePath = None
        else:
            templatePath = self.checkTemplate_(args.source)
        
        if not sourcePath and not templatePath:
            self.failWithMessage_(u"No valid OS X installer or AutoDMG template found at %s" % args.source)
            return 1
        
        if templatePath:
            template = IEDTemplate.alloc().init()
            error = template.loadTemplateAndReturnError_(templatePath)
            if error:
                self.failWithMessage_(u"Couldn't load template from %s: %s" % (templatePath, error))
                return 1
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
            template.setAdditionalPackages_(args.packages)
        
        if not template.sourcePath:
            self.failWithMessage_(u"No source path")
            return 1
        if not template.outputPath:
            self.failWithMessage_(u"No output path")
            return 1
        
        template.resolvePackages()
        
        print (u"Installer: %s" % (template.sourcePath)).encode("utf-8")
        print (u"Output Path: %s" % (template.outputPath)).encode("utf-8")
        print (u"Volume Name: %s" % (template.volumeName)).encode("utf-8")
        for package in template.packagesToInstall:
            print (u"Installing Package: %s" % (package.name())).encode("utf-8")
        
        self.busy = True
        self.workflow.setSource_(template.sourcePath)
        self.waitBusy()
        if self.hasFailed:
            return 1
        
        if os.path.exists(template.outputPath):
            if args.force:
                try:
                    os.unlink(template.outputPath)
                except OSError as e:
                    self.failWithMessage_(u"Couldn't remove %s: %s" % (template.outputPath, unicode(e)))
                    return 1
            else:
                self.failWithMessage_(u"%s already exists" % template.outputPath)
                return 1
        
        self.busy = True
        self.workflow.setPackagesToInstall_(template.packagesToInstall)
        self.workflow.setOutputPath_(template.outputPath)
        #self.workflow.setVolumeName_(template.volumeName)
        self.workflow.start()
        self.waitBusy()
        if self.hasFailed:
            return 1
        
        return 0
    
    def waitBusy(self):
        runLoop = NSRunLoop.currentRunLoop()
        while self.busy:
            nextfire = runLoop.limitDateForMode_(NSDefaultRunLoopMode)
            if not self.busy:
                break
            if not runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, nextfire):
                self.failWithMessage_(u"runMode:beforeDate: failed")
                break
    
    def checkTemplate_(self, path):
        path = IEDUtil.resolvePath(path)
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
    
    # Workflow delegate methods.
    
    def ejectingSource(self):
        print u"Ejecting source…".encode("utf-8")
    
    def examiningSource_(self, path):
        print u"Examining source…".encode("utf-8")
    
    def foundSourceForIcon_(self, path):
        pass
    
    def sourceSucceeded_(self, info):
        self.installerName = info[u"name"]
        self.installerVersion = info[u"version"]
        self.installerBuild = info[u"build"]
        print (u"Found installer: %s %s %s" % (info[u"name"], info[u"version"], info[u"build"])).encode("utf-8")
        #self.updateController.loadProfileForVersion_build_(info[u"version"], info[u"build"])
        self.busy = False
    
    def sourceFailed_text_(self, message, text):
        self.failWithMessage_(u"Source failed: %s" % message)
        self.failWithMessage_(u"    %s" % text)
    
    
    
    def buildStartingWithOutput_(self, outputPath):
        self.busy = True
    
    def buildSetTotalWeight_(self, totalWeight):
        self.progressMax = totalWeight
    
    def buildSetPhase_(self, phase):
        print (u"phase: %s" % phase).encode(u"utf-8")
        LogNotice(u"phase: %@", phase)
    
    def buildSetProgress_(self, progress):
        percent = 100.0 * progress / self.progressMax
        if abs(percent - self.lastProgress) >= 0.1:
            LogNotice(u"progress: %.1f%%", percent)
        self.lastProgress = percent
    
    def buildSetProgressMessage_(self, message):
        if message != self.lastMessage:
            LogNotice(u"message: %@", message)
            self.lastMessage = message
    
    def buildSucceeded(self):
        LogNotice(u"Build successful")
    
    def buildFailed_details_(self, message, details):
        self.failWithMessage_(u"Build failed: %s" % message)
        self.failWithMessage_(u"    %s" % details)
    
    def buildStopped(self):
        self.busy = False

#-*- coding: utf-8 -*-
#
#  IEDTemplate.py
#  AutoDMG
#
#  Created by Per Olofsson on 2014-02-26.
#  Copyright (c) 2014 University of Gothenburg. All rights reserved.
#

import objc
from Foundation import *

import os.path
from IEDLog import *
from IEDUtil import *
from IEDPackage import *


class IEDTemplate(NSObject):
    
    def init(self):
        self = super(IEDTemplate, self).init()
        if self is None:
            return None
        
        self.sourcePath = None
        self.outputPath = None
        self.applyUpdates = False
        self.additionalPackages = NSMutableArray.alloc().init()
        self.volumeName = u"Macintosh HD"
        self.packagesToInstall = None
        
        return self
    
    def initWithSourcePath_(self, path):
        self = self.init()
        if self is None:
            return None
        
        self.setSourcePath_(path)
        
        return self
    
    def loadTemplateAndReturnError_(self, path):
        plist = NSDictionary.dictionaryWithContentsOfFile_(path)
        if not plist:
            error = u"Couldn't read dictionary from plist at %s" % (path)
            LogDebug(u"%@", error)
            return error
        
        for key in plist.keys():
            if key == u"IncludeTemplates":
                for includePath in plist[u"IncludeTemplates"]:
                    LogInfo(u"Including template %@", includePath)
                    error = self.loadTemplateAndReturnError_(includePath)
                    if error:
                        return error
            elif key == u"SourcePath":
                self.setSourcePath_(plist[u"SourcePath"])
            elif key == u"ApplyUpdates":
                self.setApplyUpdates_(plist[u"ApplyUpdates"])
            elif key == u"AdditionalPackages":
                if not self.setAdditionalPackages_(plist[u"AdditionalPackages"]):
                    return u"Additional packages failed verification"
            elif key == u"OutputPath":
                self.setOutputPath_(plist[u"OutputPath"])
            elif key == u"VolumeName":
                self.setVolumeName_(plist[u"VolumeName"])
            
            else:
                LogWarning(u"Unknown key '%@' in template", key)
        
        return None
    
    def setSourcePath_(self, path):
        LogInfo(u"Setting source path to '%@'", path)
        self.sourcePath = IEDUtil.resolvePath(os.path.expanduser(path))
    
    def setApplyUpdates_(self, shouldApplyUpdates):
        LogInfo(u"Setting apply updates to '%@'", shouldApplyUpdates)
        self.applyUpdates = shouldApplyUpdates
        LogNotice(u"applyUpdates not implemented")
    
    def setAdditionalPackages_(self, packagePaths):
        for packagePath in packagePaths:
            path = IEDUtil.resolvePath(os.path.expanduser(packagePath))
            if not path:
                LogError(u"Package '%@' not found", packagePath)
                return False
            if path not in self.additionalPackages:
                LogInfo(u"Adding '%@' to additional packages", path)
                self.additionalPackages.append(IEDUtil.resolvePath(path))
            else:
                LogInfo(u"Skipping duplicate package '%@'", path)
        return True
    
    def setOutputPath_(self, path):
        LogInfo(u"Setting output path to '%@'", path)
        self.outputPath = os.path.expanduser(path)
    
    def setVolumeName_(self, name):
        LogInfo(u"Setting volume name to '%@'", name)
        self.volumeName = name
        LogNotice(u"volumeName not implemented")
    
    def resolvePackages(self):
        if self.applyUpdates:
            LogWarning(u"Installing updates with a template isn't implemented")
        self.packagesToInstall = list()
        for path in self.additionalPackages:
            package = IEDPackage.alloc().init()
            package.setName_(os.path.basename(path))
            package.setPath_(path)
            package.setSize_(IEDUtil.getPackageSize_(path))
            package.setImage_(NSWorkspace.sharedWorkspace().iconForFile_(path))
            self.packagesToInstall.append(package)

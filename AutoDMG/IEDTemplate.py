# -*- coding: utf-8 -*-
#
#  IEDTemplate.py
#  AutoDMG
#
#  Created by Per Olofsson on 2014-02-26.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

import objc
from Foundation import *

import os.path
import re
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
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
        self.additionalPackageError = None
        self.volumeName = "Macintosh HD"
        self.volumeSize = None
        self.finalizeAsrImagescan = True
        self.packagesToInstall = None
        
        self.loadedTemplates = set()
        
        return self
    
    def __repr__(self):
        return "\n".join(("<IEDTemplate",
                          "    sourcePath=%s" % repr(self.sourcePath),
                          "    outputPath=%s" % repr(self.outputPath),
                          "    applyUpdates=%s" % repr(self.applyUpdates),
                          "    additionalPackages=(%s)" % ", ".join(repr(x) for x in self.additionalPackages),
                          "    volumeName=%s" % repr(self.volumeName),
                          "    volumeSize=%s" % repr(self.volumeSize),
                          "    finalizeAsrImagescan=%s" % repr(self.finalizeAsrImagescan),
                          ">"))
    
    def initWithSourcePath_(self, path):
        self = self.init()
        if self is None:
            return None
        
        self.setSourcePath_(path)
        
        return self
    
    def saveTemplateAndReturnError_(self, path):
        plist = NSMutableDictionary.alloc().init()
        plist["TemplateFormat"] = self.templateFormat = "1.0"
        plist["AdditionalPackages"] = self.additionalPackages
        plist["ApplyUpdates"] = self.applyUpdates
        plist["VolumeName"] = self.volumeName
        if self.sourcePath:
            plist["SourcePath"] = self.sourcePath
        if self.outputPath:
            plist["OutputPath"] = self.outputPath
        if self.volumeSize:
            plist["VolumeSize"] = self.volumeSize
        if not self.finalizeAsrImagescan:
            plist["FinalizeAsrImagescan"] = self.finalizeAsrImagescan
        if plist.writeToFile_atomically_(path, False):
            return None
        else:
            error = "Couldn't write dictionary to plist at %s" % (path)
            LogWarning("%@", error)
            return error
    
    def loadTemplateAndReturnError_(self, path):
        if path in self.loadedTemplates:
            return "%s included recursively" % path
        else:
            self.loadedTemplates.add(path)
        
        plist = NSDictionary.dictionaryWithContentsOfFile_(path)
        if not plist:
            error = "Couldn't read dictionary from plist at %s" % (path)
            LogWarning("%@", error)
            return error
        
        templateFormat = plist.get("TemplateFormat", "1.0")
        
        if templateFormat != "1.0":
            LogWarning("Unknown format version %@", templateFormat)
        
        for key in plist.iterkeys():
            if key == "IncludeTemplates":
                for includePath in plist["IncludeTemplates"]:
                    LogInfo("Including template %@", includePath)
                    error = self.loadTemplateAndReturnError_(includePath)
                    if error:
                        return error
            elif key == "SourcePath":
                self.setSourcePath_(plist["SourcePath"])
            elif key == "ApplyUpdates":
                self.setApplyUpdates_(plist["ApplyUpdates"])
            elif key == "AdditionalPackages":
                if not self.setAdditionalPackages_(plist["AdditionalPackages"]):
                    msg = "Additional packages failed verification"
                    if self.additionalPackageError:
                        msg += ":\n" + self.additionalPackageError
                    return msg
            elif key == "OutputPath":
                self.setOutputPath_(plist["OutputPath"])
            elif key == "VolumeName":
                self.setVolumeName_(plist["VolumeName"])
            elif key == "VolumeSize":
                self.setVolumeSize_(plist["VolumeSize"])
            elif key == "FinalizeAsrImagescan":
                self.setFinalizeAsrImagescan_(plist["FinalizeAsrImagescan"])
            elif key == "TemplateFormat":
                pass
            
            else:
                LogWarning("Unknown key '%@' in template", key)
        
        return None
    
    def setSourcePath_(self, path):
        LogInfo("Setting source path to '%@'", path)
        self.sourcePath = IEDUtil.resolvePath_(os.path.expanduser(path))
    
    def setApplyUpdates_(self, shouldApplyUpdates):
        LogInfo("Setting apply updates to '%@'", shouldApplyUpdates)
        self.applyUpdates = shouldApplyUpdates
    
    def setAdditionalPackages_(self, packagePaths):
        self.additionalPackageError = None
        for packagePath in packagePaths:
            path = IEDUtil.resolvePath_(os.path.abspath(os.path.expanduser(packagePath)))
            if not os.path.exists(path):
                self.additionalPackageError = "Package '%s' not found" % packagePath
                LogError("'%@'", self.additionalPackageError)
                return False
            name, ext = os.path.splitext(path)
            if ext.lower() not in IEDUtil.PACKAGE_EXTENSIONS:
                self.additionalPackageError = "'%s' is not valid software package" % packagePath
                LogError("'%@'", self.additionalPackageError)
                return False
            if path not in self.additionalPackages:
                LogInfo("Adding '%@' to additional packages", path)
                self.additionalPackages.append(IEDUtil.resolvePath_(path))
            else:
                LogInfo("Skipping duplicate package '%@'", path)
        return True
    
    def setOutputPath_(self, path):
        LogInfo("Setting output path to '%@'", path)
        self.outputPath = os.path.abspath(os.path.expanduser(path))
    
    def setVolumeName_(self, name):
        LogInfo("Setting volume name to '%@'", name)
        self.volumeName = name
    
    def setVolumeSize_(self, size):
        LogInfo("Setting volume size to '%d'", size)
        self.volumeSize = size
    
    def setFinalizeAsrImagescan_(self, finalizeAsrImagescan):
        LogInfo("Setting 'Finalize: Scan for restore to '%@'", finalizeAsrImagescan)
        self.finalizeAsrImagescan = finalizeAsrImagescan

    def resolvePackages(self):
        self.packagesToInstall = list()
        for path in self.additionalPackages:
            package = IEDPackage.alloc().init()
            package.setName_(os.path.basename(path))
            package.setPath_(path)
            package.setSize_(IEDUtil.getPackageSize_(path))
            package.setImage_(NSWorkspace.sharedWorkspace().iconForFile_(path))
            self.packagesToInstall.append(package)
    
    re_keyref = re.compile(r'%(?P<key>[A-Z][A-Z_0-9]*)%')
    
    def resolveVariables_(self, variables):
        formatter = NSDateFormatter.alloc().init()
        formatter.setDateFormat_("yyMMdd")
        variables["DATE"] = formatter.stringFromDate_(NSDate.date())
        formatter.setDateFormat_("HHmmss")
        variables["TIME"] = formatter.stringFromDate_(NSDate.date())
        
        def getvar(m):
            try:
                return variables[m.group("key")]
            except KeyError as err:
                LogWarning("Template references undefined variable: %%%@%%", m.group("key"))
                return "%%%s%%" % m.group("key")
        
        self.volumeName = self.re_keyref.sub(getvar, self.volumeName)
        self.outputPath = self.re_keyref.sub(getvar, self.outputPath)

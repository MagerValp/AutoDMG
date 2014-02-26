#-*- coding: utf-8 -*-
#
#  IEDUtil.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
from Carbon.File import *
import MacOS

import os.path


class IEDUtil(NSObject):
    
    VERSIONPLIST_PATH = u"System/Library/CoreServices/SystemVersion.plist"
    
    @classmethod
    def readSystemVersion_(cls, rootPath):
        plist = NSDictionary.dictionaryWithContentsOfFile_(os.path.join(rootPath, cls.VERSIONPLIST_PATH))
        name = plist[u"ProductName"]
        version = plist[u"ProductUserVisibleVersion"]
        build = plist[u"ProductBuildVersion"]
        return (name, version, build)
    
    @classmethod
    def getAppVersion(cls):
        bundle = NSBundle.mainBundle()
        version = bundle.objectForInfoDictionaryKey_(u"CFBundleShortVersionString")
        build = bundle.objectForInfoDictionaryKey_(u"CFBundleVersion")
        return (version, build)
    
    @classmethod
    def resolvePath(cls, path):
        """Expand symlinks and resolve aliases."""
        try:
            fsref, isFolder, wasAliased = FSResolveAliasFile(os.path.realpath(path), 1)
            return fsref.as_pathname().decode(u"utf-8")
        except MacOS.Error as e:
            return None


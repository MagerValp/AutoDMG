#-*- coding: utf-8 -*-
#
#  IEDUtil.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *

import os.path


class IEDUtil(NSObject):
    
    VERSIONPLIST_PATH = u"System/Library/CoreServices/SystemVersion.plist"
    
    @classmethod
    def readSystemVersion(cls, rootPath):
        plist = NSDictionary.dictionaryWithContentsOfFile_(os.path.join(rootPath, cls.VERSIONPLIST_PATH))
        name = plist[u"ProductName"]
        version = plist[u"ProductUserVisibleVersion"]
        build = plist[u"ProductBuildVersion"]
        return (name, version, build)

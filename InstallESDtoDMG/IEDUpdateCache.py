#-*- coding: utf-8 -*-
#
#  IEDUpdateCache.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
import os

class IEDUpdateCache(NSObject):
    """Managed updates cached on disk in the Application Support directory."""
    
    def init(self):
        self = super(IEDUpdateCache, self).init()
        if self is None:
            return None
        
        self.updates = {
            u"18636c06f0db5b326752628fb7a2dfa3ce077ae1": {
                u"name": u"OS X Mountain Lion 10.8.5 Supplemental Update",
                u"size": 19648899,
            },
            u"66b75a92d234affaed19484810d8dc53ed4608dd": {
                u"name": u"iTunes 11.1.1",
                u"size": 225609082,
            },
            u"ce78f9a916b91ec408c933bd0bde5973ca8a2dc4": {
                u"name": u"Java for OS X 2013-005",
                u"size": 67090041,
            },
            u"7cb449454ef5c2cf478a2a5394f652a9705c9481": {
                u"name": u"AirPort Utility 6.3.1 for Mac",
                u"size": 22480138,
            },
        }
        
        fm = NSFileManager.defaultManager()
        url, error = fm.URLForDirectory_inDomain_appropriateForURL_create_error_(NSApplicationSupportDirectory,
                                                                                 NSUserDomainMask,
                                                                                 None,
                                                                                 True,
                                                                                 None)
        self.updateDir = os.path.join(url.path(), u"AutoDMG", u"Updates")
        if not os.path.exists(self.updateDir):
            try:
                os.makedirs(self.updateDir)
            except OSError as e:
                NSLog(u"Failed to create %@: %@", self.updateDir, unicode(e))
        return self
    
    def isCached_(self, sha1):
        return sha1 in self.updates and os.path.exists(self.getUpdatePath_(sha1))
    
    def getUpdatePath_(self, sha1):
        if sha1 in self.updates:
            return os.path.join(self.updateDir, sha1)
        else:
            return None

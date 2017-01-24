# -*- coding: utf-8 -*-
#
#  IEDPanelPathManager.py
#  AutoDMG
#
#  Created by Per Olofsson on 2016-12-06.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *

# No logging here, since IEDLog uses us.
#from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


defaults = NSUserDefaults.standardUserDefaults()


class IEDPanelPathManager(NSObject):
    
    @classmethod
    def loadPathForName_(cls, name):
        path = defaults.stringForKey_("Last%sDir" % name)
        if path:
            #LogDebug(u"Load path for %@ = '%@'", name, path)
            defaults.setObject_forKey_(path, "NSNavLastRootDirectory")
    
    @classmethod
    def savePathForName_(cls, name):
        path = defaults.stringForKey_("NSNavLastRootDirectory")
        if path:
            #LogDebug(u"Save path for %@ = '%@'", name, path)
            defaults.setObject_forKey_(path, "Last%sDir" % name)
    

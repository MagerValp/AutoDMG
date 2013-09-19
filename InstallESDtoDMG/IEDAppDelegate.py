#-*- coding: utf-8 -*-
#
#  InstallESDtoDMGAppDelegate.py
#  InstallESDtoDMG
#
#  Created by Pelle on 2013-09-19.
#  Copyright Göteborgs universitet 2013. All rights reserved.
#

from Foundation import *
from AppKit import *

class IEDAppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, sender):
        NSLog("Application did finish launching.")

#-*- coding: utf-8 -*-
#
#  InstallESDtoDMGAppDelegate.py
#  InstallESDtoDMG
#
#  Created by Pelle on 2013-09-19.
#  Copyright Per Olofsson, University of Gothenburg 2013. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

class IEDAppDelegate(NSObject):
    
    def applicationDidFinishLaunching_(self, sender):
        pass

    @IBAction
    def selectSource_(self, filename):
        NSLog(u"Source selected: %@", filename)

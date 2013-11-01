#-*- coding: utf-8 -*-
#
#  main.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright Per Olofsson, University of Gothenburg 2013. All rights reserved.
#

#import modules required by application
import objc
import Foundation
import AppKit

objc.setVerbose(1)

from PyObjCTools import AppHelper

# import modules containing classes required to start application and load MainMenu.nib
import IEDAppDelegate
import IEDController
import IEDSourceSelector
import IEDAddPkgController
import IEDAppVersionController


# pass control to AppKit
AppHelper.runEventLoop()

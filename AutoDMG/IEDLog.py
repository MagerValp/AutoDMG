#-*- coding: utf-8 -*-
#
#  IEDLog.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-25.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#


from Foundation import *


IEDLogLevelCritical = 0
IEDLogLevelError    = 1
IEDLogLevelWarning  = 2
IEDLogLevelNotice   = 3
IEDLogLevelInfo     = 4
IEDLogLevelDebug    = 5


class IEDLog(NSObject):
    
    logLevel = IEDLogLevelWarning


def LogDebug(*args):
    if IEDLog.logLevel >= IEDLogLevelDebug:
        NSLog(*args)

def LogInfo(*args):
    if IEDLog.logLevel >= IEDLogLevelInfo:
        NSLog(*args)

def LogNotice(*args):
    if IEDLog.logLevel >= IEDLogLevelNotice:
        NSLog(*args)

def LogWarning(*args):
    if IEDLog.logLevel >= IEDLogLevelWarning:
        NSLog(*args)

def LogError(*args):
    if IEDLog.logLevel >= IEDLogLevelError:
        NSLog(*args)

def LogCritical(*args):
        NSLog(*args)


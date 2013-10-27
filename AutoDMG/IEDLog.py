#-*- coding: utf-8 -*-
#
#  IEDLog.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-25.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#


from Foundation import *


IEDLogLevelEmergency = 0
IEDLogLevelAlert     = 1
IEDLogLevelCritical  = 2
IEDLogLevelError     = 3
IEDLogLevelWarning   = 4
IEDLogLevelNotice    = 5
IEDLogLevelInfo      = 6
IEDLogLevelDebug     = 7


class IEDLog(NSObject):
    
    logLevel = IEDLogLevelNotice


def LogMessage(level, message):
    if IEDLog.logLevel >= level:
        NSLog(u"%@", message)

def LogDebug(*args):
    LogMessage(IEDLogLevelDebug, NSString.stringWithFormat_(*args))

def LogInfo(*args):
    LogMessage(IEDLogLevelInfo, NSString.stringWithFormat_(*args))

def LogNotice(*args):
    LogMessage(IEDLogLevelNotice, NSString.stringWithFormat_(*args))

def LogWarning(*args):
    LogMessage(IEDLogLevelWarning, NSString.stringWithFormat_(*args))

def LogError(*args):
    LogMessage(IEDLogLevelError, NSString.stringWithFormat_(*args))

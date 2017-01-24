# -*- coding: utf-8 -*-
#
#  IEDLogLine.py
#  AutoDMG
#
#  Created by Pelle on 2013-10-28.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *


class IEDLogLine(NSObject):
    
    def init(self):
        self = super(IEDLogLine, self).init()
        if self is None:
            return None
        
        self._date = NSDate.date()
        self._message = ""
        self._level = 0
        
        return self
    
    def initWithMessage_level_(self, message, level):
        self = self.init()
        if self is None:
            return None
        
        self._message = message
        self._level = level
        
        return self
    
    def date(self):
        return self._date
    
    def setDate(self, date):
        self._date = date
    
    def message(self):
        return self._message
    
    def setMessage(self, message):
        self._message = message
    
    def level(self):
        return self._level
    
    def setLevel(self, level):
        self._level = level

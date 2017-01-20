# -*- coding: utf-8 -*-
#
#  IEDSourceSelector.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet, classAddMethods

import os.path
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
from IEDUtil import *


def awakeFromNib(self):
    self.registerForDraggedTypes_([NSFilenamesPboardType])
    self.startAcceptingDrag()

def setDelegate_(self, _delegate):
    self._delegate = _delegate

def startAcceptingDrag(self):
    self.dragEnabled = True

def stopAcceptingDrag(self):
    self.dragEnabled = False

def checkSource_(self, sender):
    pboard = sender.draggingPasteboard()
    filenames = pboard.propertyListForType_(NSFilenamesPboardType)
    if len(filenames) != 1:
        return None
    path = IEDUtil.resolvePath_(filenames[0])
    if IEDUtil.mightBeSource_(path):
        return path
    else:
        return None

def draggingEntered_(self, sender):
    self.dragOperation = NSDragOperationNone
    if self.dragEnabled:
        if self.checkSource_(sender):
            self.dragOperation = NSDragOperationCopy
    return self.dragOperation

def draggingUpdated_(self, sender):
    return self.dragOperation

def performDragOperation_(self, sender):
    filename = self.checkSource_(sender)
    if filename:
        self._delegate.acceptSource_(filename)
        return True
    else:
        return False


class IEDBoxSourceSelector(NSBox):
    pass
classAddMethods(IEDBoxSourceSelector, [
    awakeFromNib,
    setDelegate_,
    startAcceptingDrag,
    stopAcceptingDrag,
    checkSource_,
    draggingEntered_,
    draggingUpdated_,
    performDragOperation_,
])

class IEDImageViewSourceSelector(NSImageView):
    pass
classAddMethods(IEDImageViewSourceSelector, [
    awakeFromNib,
    setDelegate_,
    startAcceptingDrag,
    stopAcceptingDrag,
    checkSource_,
    draggingEntered_,
    draggingUpdated_,
    performDragOperation_,
])

class IEDTextFieldSourceSelector(NSTextField):
    pass
classAddMethods(IEDTextFieldSourceSelector, [
    awakeFromNib,
    setDelegate_,
    startAcceptingDrag,
    stopAcceptingDrag,
    checkSource_,
    draggingEntered_,
    draggingUpdated_,
    performDragOperation_,
])

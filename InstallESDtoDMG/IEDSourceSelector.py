#-*- coding: utf-8 -*-
#
#  IEDSourceSelector.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

import os.path


class IEDSourceSelector(NSImageView):
    
    delegate = None
    selectedSource = None
    dragOperation = None
    
    def initWithFrame_(self, frame):
        self = super(IEDSourceSelector, self).initWithFrame_(frame)
        if self:
            self.registerForDraggedTypes_([NSFilenamesPboardType])
        return self
    
    def setDelegate_(self, delegate):
        self.delegate = delegate
    
    def checkSource_(self, sender):
        pboard = sender.draggingPasteboard()
        filenames = pboard.propertyListForType_(NSFilenamesPboardType)
        if len(filenames) == 1:
            if os.path.exists(os.path.join(filenames[0],
                              u"Contents/SharedSupport/InstallESD.dmg")):
                return filenames[0]
        return None
    
    def draggingEntered_(self, sender):
        if self.checkSource_(sender):
            self.dragOperation = NSDragOperationLink
        else:
            self.dragOperation = NSDragOperationNone
        return self.dragOperation
    
    def draggingUpdated_(self, sender):
        return self.dragOperation
    
    def performDragOperation_(self, sender):
        filename = self.checkSource_(sender)
        if filename:
            self.selectedSource = filename
            self.delegate.acceptSource_(filename)
            return True
        else:
            return False

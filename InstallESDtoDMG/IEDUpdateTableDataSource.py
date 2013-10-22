#-*- coding: utf-8 -*-
#
#  IEDUpdateTableDataSource.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *


class IEDUpdateTableDataSource(NSObject):
    
    def initWithProfileController_updateCache_(self, pc, cache):
        self = super(IEDUpdateTableDataSource, self).init()
        if self is None:
            return None
        
        self.profileController = pc
        self.updateCache = cache
        self.updates = list()
        self.downloadSize = 0
        self.downloadCount = 0
        
        self.cachedImage = NSImage.imageNamed_(u"Package")
        self.uncachedImage = NSImage.imageNamed_(u"Package blue arrow")
        
        return self
    
    def loadProfileForVersion_build_(self, version, build):
        profile = self.profileController.profileForVersion_Build_(version, build)
        if profile:
            self.updates = profile
        else:
            self.updates = list()
        self.countDownloads()
    
    def countDownloads(self):
        for update in self.updates:
            if not self.updateCache.isCached_(update[u"sha1"]):
                self.downloadCount += 1
                self.downloadSize += update[u"size"]
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.updates)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        if column.identifier() == u"image":
            update = self.updates[row]
            if self.updateCache.isCached_(update[u"sha1"]):
                return self.cachedImage
            else:
                return self.uncachedImage
        elif column.identifier() == u"name":
            return self.updates[row][u"name"]



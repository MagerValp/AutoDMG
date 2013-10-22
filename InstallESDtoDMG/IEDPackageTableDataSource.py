#-*- coding: utf-8 -*-
#
#  IEDPackageTableDataSource.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright (c) 2013 University of Gothenburg. All rights reserved.
#

from Foundation import *
from AppKit import *
import os.path


class IEDPackageTableDataSource(NSObject):
    
    def init(self):
        self = super(IEDPackageTableDataSource, self).init()
        if self is None:
            return None
        
        self.packages = list()
        self.pkgImage = NSImage.imageNamed_(u"Package")
        
        return self
    
    def packagePaths(self):
        return [pkg[u"path"] for pkg in self.packages]
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.packages)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        return self.packages[row][column.identifier()]
    
    def tableView_setObjectValue_forTableColumn_row_(self, tableView, obj, column, row):
        self.packages.insert(row, obj)
    
    def tableView_validateDrop_proposedRow_proposedDropOperation_(self, tableView, info, row, operation):
        if info.draggingSource() == tableView:
            return NSDragOperationMove
        pboard = info.draggingPasteboard()
        paths = pboard.propertyListForType_(NSFilenamesPboardType)
        if not paths:
            return NSDragOperationNone
        for path in paths:
            name, ext = os.path.splitext(path)
            if ext.lower() not in (u".pkg", u".mpkg"):
                return NSDragOperationNone
        return NSDragOperationCopy
    
    def tableView_acceptDrop_row_dropOperation_(self, tableView, info, row, operation):
        pboard = info.draggingPasteboard()
        # If the source is the tableView, we're reordering packages within the
        # table and the pboard contains the source row indices.
        if info.draggingSource() == tableView:
            indices = [int(i) for i in pboard.propertyListForType_(NSStringPboardType).split(u",")]
            for i in indices:
                self.packages[row], self.packages[i] = self.packages[i], self.packages[row]
        else:
            # Otherwise it's a list of paths to add to the table.
            paths = pboard.propertyListForType_(NSFilenamesPboardType)
            for i, path in enumerate(paths):
                package = {
                    u"image": NSWorkspace.sharedWorkspace().iconForFile_(path),
                    u"path": path,
                    u"name": os.path.basename(path),
                }
                self.packages.insert(row + i, package)
        tableView.reloadData()
        return True
    
    def tableView_writeRowsWithIndexes_toPasteboard_(self, tableView, rowIndexes, pboard):
        # When reordering packages put a list of indices as a string onto the pboard.
        indices = list()
        index = rowIndexes.firstIndex()
        while index != NSNotFound:
            indices.append(index)
            index = rowIndexes.indexGreaterThanIndex_(index)
        pboard.declareTypes_owner_([NSStringPboardType], self)
        pboard.setPropertyList_forType_(u",".join(unicode(i) for i in indices), NSStringPboardType)
        return True



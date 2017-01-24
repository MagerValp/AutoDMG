# -*- coding: utf-8 -*-
#
#  IEDAddPkgController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet
import os.path

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage, LogException
from IEDUtil import *
from IEDPackage import *


class IEDAddPkgController(NSObject):
    
    addPkgLabel = IBOutlet()
    tableView = IBOutlet()
    removeButton = IBOutlet()
    
    movedRowsType = "se.gu.it.AdditionalPackages"
    
    def init(self):
        self = super(IEDAddPkgController, self).init()
        if self is None:
            return None
        
        self.packages = list()
        self.packagePaths = set()
        
        return self
    
    def awakeFromNib(self):
        self.tableView.setDataSource_(self)
        self.tableView.registerForDraggedTypes_([NSFilenamesPboardType, IEDAddPkgController.movedRowsType])
        self.dragEnabled = True
    
    # Helper methods.
    
    def disableControls(self):
        self.dragEnabled = False
        self.addPkgLabel.setTextColor_(NSColor.disabledControlTextColor())
        self.tableView.setEnabled_(False)
        self.removeButton.setEnabled_(False)
    
    def enableControls(self):
        self.dragEnabled = True
        self.addPkgLabel.setTextColor_(NSColor.controlTextColor())
        self.tableView.setEnabled_(True)
        self.removeButton.setEnabled_(True)
    
    
    
    # External state of controller.
    
    def packagesToInstall(self):
        return self.packages
    
    
    
    # Loading.
    
    def replacePackagesWithPaths_(self, packagePaths):
        del self.packages[:]
        self.packagePaths.clear()
        for path in packagePaths:
            package = IEDPackage.alloc().init()
            package.setName_(os.path.basename(path))
            package.setPath_(path)
            package.setSize_(IEDUtil.getPackageSize_(path))
            package.setImage_(NSWorkspace.sharedWorkspace().iconForFile_(path))
            self.packages.append(package)
            self.packagePaths.add(path)
        self.tableView.reloadData()
    
    
    
    # Act on remove button.
    
    @LogException
    @IBAction
    def removeButtonClicked_(self, sender):
        indexes = self.tableView.selectedRowIndexes()
        row = indexes.lastIndex()
        while row != NSNotFound:
            self.packagePaths.remove(self.packages[row].path())
            del self.packages[row]
            row = indexes.indexLessThanIndex_(row)
        self.tableView.reloadData()
        self.tableView.deselectAll_(self)
    
    
    
    # We're an NSTableViewDataSource.
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.packages)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        # FIXME: Use bindings.
        if column.identifier() == "image":
            return self.packages[row].image()
        elif column.identifier() == "name":
            return self.packages[row].name()
    
    def tableView_validateDrop_proposedRow_proposedDropOperation_(self, tableView, info, row, operation):
        if not self.dragEnabled:
            return NSDragOperationNone
        if info.draggingSource() == tableView:
            return NSDragOperationMove
        pboard = info.draggingPasteboard()
        paths = [IEDUtil.resolvePath_(path) for path in pboard.propertyListForType_(NSFilenamesPboardType)]
        if not paths:
            return NSDragOperationNone
        for path in paths:
            # Don't allow multiple copies.
            if path in self.packagePaths:
                return NSDragOperationNone
            # Ensure the file extension is valid for additonal packages.
            name, ext = os.path.splitext(path)
            if ext.lower() not in IEDUtil.PACKAGE_EXTENSIONS:
                return NSDragOperationNone
        return NSDragOperationCopy
    
    def tableView_acceptDrop_row_dropOperation_(self, tableView, info, row, operation):
        if not self.dragEnabled:
            return False
        pboard = info.draggingPasteboard()
        # If the source is the tableView, we're reordering packages within the
        # table and the pboard contains the source row indexes.
        if info.draggingSource() == tableView:
            indexes = [int(i) for i in pboard.propertyListForType_(IEDAddPkgController.movedRowsType).split(",")]
            # If the rows are dropped on top of another line, and the target
            # row is below the first source row, move the target row one line
            # down.
            if (operation == NSTableViewDropOn) and (indexes[0] < row):
                rowAdjust = 1
            else:
                rowAdjust = 0
            # Move the dragged rows out from the package list into draggedRows.
            draggedRows = list()
            for i in sorted(indexes, reverse=True):
                draggedRows.insert(0, (i, self.packages.pop(i)))
            # Adjust the target row since we have removed items.
            row -= len([x for x in draggedRows if x[0] < row])
            row += rowAdjust
            # Insert them at the new place.
            for i, (index, item) in enumerate(draggedRows):
                self.packages.insert(row + i, item)
            # Select the newly moved lines.
            selectedIndexes = NSIndexSet.indexSetWithIndexesInRange_(NSMakeRange(row, len(draggedRows)))
            tableView.selectRowIndexes_byExtendingSelection_(selectedIndexes, False)
        else:
            # Otherwise it's a list of paths to add to the table.
            paths = [IEDUtil.resolvePath_(path) for path in pboard.propertyListForType_(NSFilenamesPboardType)]
            # Remove duplicates from list.
            seen = set()
            paths = [x for x in paths if x not in seen and not seen.add(x)]
            for i, path in enumerate(paths):
                package = IEDPackage.alloc().init()
                package.setName_(os.path.basename(path))
                package.setPath_(path)
                package.setSize_(IEDUtil.getPackageSize_(path))
                package.setImage_(NSWorkspace.sharedWorkspace().iconForFile_(path))
                self.packages.insert(row + i, package)
                self.packagePaths.add(path)
        tableView.reloadData()
        return True
    
    def tableView_writeRowsWithIndexes_toPasteboard_(self, tableView, rowIndexes, pboard):
        # When reordering packages put a list of indexes as a string onto the pboard.
        indexes = list()
        index = rowIndexes.firstIndex()
        while index != NSNotFound:
            indexes.append(index)
            index = rowIndexes.indexGreaterThanIndex_(index)
        pboard.declareTypes_owner_([IEDAddPkgController.movedRowsType], self)
        pboard.setPropertyList_forType_(",".join(str(i) for i in indexes), IEDAddPkgController.movedRowsType)
        return True

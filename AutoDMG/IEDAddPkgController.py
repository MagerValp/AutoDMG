#-*- coding: utf-8 -*-
#
#  IEDAddPkgController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright (c) 2013 University of Gothenburg. All rights reserved.
#

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet
import os.path
import subprocess

from IEDLog import *
from IEDPackage import *


class IEDAddPkgController(NSObject):
    
    addPkgLabel = IBOutlet()
    tableView = IBOutlet()
    removeButton = IBOutlet()
    
    movedRowsType = u"se.gu.it.AdditionalPackages"
    
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
    
    def getPackageSize_(self, path):
        p = subprocess.Popen([u"/usr/bin/du", u"-sk", path],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            LogError(u"du failed with exit code %d", p.returncode)
        else:
            return int(out.split()[0]) * 1024
    
    
    
    # External state of controller.
    
    def packagesToInstall(self):
        return self.packages
    
    
    
    # Act on remove button.
    
    @IBAction
    def removeButtonClicked_(self, sender):
        row = self.tableView.selectedRow()
        if row == -1:
            return
        self.packagePaths.remove(self.packages[row].path())
        del self.packages[row]
        self.tableView.reloadData()
    
    
    
    # We're an NSTableViewDataSource.
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.packages)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        # FIXME: Use bindings.
        if column.identifier() == u"image":
            return self.packages[row].image()
        elif column.identifier() == u"name":
            return self.packages[row].name()
    
    def tableView_validateDrop_proposedRow_proposedDropOperation_(self, tableView, info, row, operation):
        if not self.dragEnabled:
            return NSDragOperationNone
        if info.draggingSource() == tableView:
            return NSDragOperationMove
        pboard = info.draggingPasteboard()
        paths = pboard.propertyListForType_(NSFilenamesPboardType)
        if not paths:
            return NSDragOperationNone
        for path in paths:
            # Don't allow multiple copies.
            if path in self.packagePaths:
                return NSDragOperationNone
            # Ensure the file extension is pkg or mpkg.
            name, ext = os.path.splitext(path)
            if ext.lower() not in (u".pkg", u".mpkg"):
                return NSDragOperationNone
        return NSDragOperationCopy
    
    def tableView_acceptDrop_row_dropOperation_(self, tableView, info, row, operation):
        if not self.dragEnabled:
            return False
        pboard = info.draggingPasteboard()
        # If the source is the tableView, we're reordering packages within the
        # table and the pboard contains the source row indices.
        if info.draggingSource() == tableView:
            indices = [int(i) for i in pboard.propertyListForType_(IEDAddPkgController.movedRowsType).split(u",")]
            for i in indices:
                self.packages[row], self.packages[i] = self.packages[i], self.packages[row]
        else:
            # Otherwise it's a list of paths to add to the table.
            paths = pboard.propertyListForType_(NSFilenamesPboardType)
            for i, path in enumerate(paths):
                package = IEDPackage.alloc().init()
                package.setName_(os.path.basename(path))
                package.setPath_(path)
                package.setSize_(self.getPackageSize_(path))
                package.setImage_(NSWorkspace.sharedWorkspace().iconForFile_(path))
                self.packages.insert(row + i, package)
                self.packagePaths.add(path)
        tableView.reloadData()
        return True
    
    def tableView_writeRowsWithIndexes_toPasteboard_(self, tableView, rowIndexes, pboard):
        # When reordering packages put a list of indices as a string onto the pboard.
        indices = list()
        index = rowIndexes.firstIndex()
        while index != NSNotFound:
            indices.append(index)
            index = rowIndexes.indexGreaterThanIndex_(index)
        pboard.declareTypes_owner_([IEDAddPkgController.movedRowsType], self)
        pboard.setPropertyList_forType_(u",".join(unicode(i) for i in indices), IEDAddPkgController.movedRowsType)
        return True



#-*- coding: utf-8 -*-
#
#  IEDUpdateCache.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
import os
import hashlib

class IEDUpdateCache(NSObject):
    """Managed updates cached on disk in the Application Support directory."""
    
    def init(self):
        self = super(IEDUpdateCache, self).init()
        if self is None:
            return None
        
        fm = NSFileManager.defaultManager()
        url, error = fm.URLForDirectory_inDomain_appropriateForURL_create_error_(NSApplicationSupportDirectory,
                                                                                 NSUserDomainMask,
                                                                                 None,
                                                                                 True,
                                                                                 None)
        self.updateDir = os.path.join(url.path(), u"AutoDMG", u"Updates")
        if not os.path.exists(self.updateDir):
            try:
                os.makedirs(self.updateDir)
            except OSError as e:
                NSLog(u"Failed to create %@: %@", self.updateDir, unicode(e))
        return self
    
    def isCached_(self, sha1):
        return os.path.exists(self.getUpdatePath_(sha1))
    
    def getUpdatePath_(self, sha1):
        return os.path.join(self.updateDir, sha1)
    
    def getUpdateTmpPath_(self, sha1):
        return os.path.join(self.updateDir, sha1 + u".part")
    
    def notifyTarget_(self, message):
        self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                          message,
                                                                          False)
    
    def failWithErrorMessage_(self, error):
        self.notifyTarget_({u"action": u"failed",
                            u"update": self.update,
                            u"error-message": error})
    
    def downloadUpdates_withTarget_selector_(self, updates, target, selector):
        self.target = target
        self.selector = selector
        self.updates = updates
        self.downloadNextUpdate()
    
    def downloadNextUpdate(self):
        if self.updates:
            self.update = self.updates.pop(0)
            self.bytesReceived = 0
            self.notifyTarget_({u"action": u"start",
                                u"update": self.update})
            path = self.getUpdateTmpPath_(self.update[u"sha1"])
            if not NSFileManager.defaultManager().createFileAtPath_contents_attributes_(path, None, None):
                error = u"Couldn't create temporary file at %s" % path
                self.failWithErrorMessage_(error)
                return
            self.fileHandle = NSFileHandle.fileHandleForWritingAtPath_(path)
            if not self.fileHandle:
                error = u"Couldn't open %s for writing" % path
                self.failWithErrorMessage_(error)
                return
            url = NSURL.URLWithString_(self.update[u"url"])
            request = NSURLRequest.requestWithURL_(url)
            NSURLConnection.connectionWithRequest_delegate_(request, self)
        else:
            self.notifyTarget_({u"action": u"alldone"})
    
    def connection_didFailWithError_(self, connection, error):
        NSLog(u"%@ failed: %@", self.update[u"name"], error)
        self.fileHandle.closeFile()
        self.failWithErrorMessage_(error.localizedDescription())
    
    def connection_didReceiveResponse_(self, connection, response):
        NSLog(u"%@ status code %d", self.update[u"name"], response.statusCode())
        self.notifyTarget_({u"action": u"response",
                            u"update": self.update,
                            u"response": response})
    
    def connection_didReceiveData_(self, connection, data):
        try:
            self.fileHandle.writeData_(data)
        except BaseException as e:
            NSLog(u"Write error: %@", unicode(e))
            connection.cancel()
            error = u"Writing to %s failed: %s" % (self.getUpdateTmpPath_(self.update[u"sha1"]), unicode(e))
            self.fileHandle.closeFile()
            self.failWithErrorMessage_(error)
            return
        self.bytesReceived += data.length()
        self.notifyTarget_({u"action": u"data",
                            u"update": self.update,
                            u"bytes-received": self.bytesReceived})
    
    def connectionDidFinishLoading_(self, connection):
        NSLog(u"%@ finished downloading to %@", self.update[u"name"], self.getUpdateTmpPath_(self.update[u"sha1"]))
        self.fileHandle.closeFile()
        self.performSelectorInBackground_withObject_(self.calculateChecksum_, None)
    
    def calculateChecksum_(self, args):
        self.notifyTarget_({u"action": u"checksumming",
                            u"update": self.update})
        sha1 = self.update[u"sha1"]
        src = self.getUpdateTmpPath_(sha1)
        dst = self.getUpdatePath_(sha1)
        
        m = hashlib.sha1()
        bytesRead = 0
        with open(src) as f:
            while True:
                data = f.read(1024 * 1024)
                if not data:
                    break
                m.update(data)
                bytesRead += len(data)
                self.notifyTarget_({u"action": u"checksum-progress",
                                    u"bytes-read": bytesRead,
                                    u"update": self.update})
        if m.hexdigest() != sha1:
            self.failWithErrorMessage_(u"Expected sha1 checksum %s but got %s" % (sha1.lower(), m.hexdigest().lower()))
            return
        try:
            os.rename(src, dst)
        except OSError as e:
            self.failWithErrorMessage_(u"Failed when moving download to %s: %s" % (dst, unicode(e)))
            return
        self.notifyTarget_({u"action": u"checksum-ok",
                            u"update": self.update})
        self.performSelectorOnMainThread_withObject_waitUntilDone_(self.checksumOK_, None, False)
    
    def checksumOK_(self, args):
        self.downloadNextUpdate()


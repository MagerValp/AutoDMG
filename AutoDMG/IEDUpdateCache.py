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
    
    def downloadUpdates_withTarget_selector_(self, updates, target, selector):
        self.target = target
        self.selector = selector
        self.updates = updates
        self.downloadNextUpdate()
    
    def downloadNextUpdate(self):
        if self.updates:
            self.update = self.updates.pop(0)
            self.bytesReceived = 0
            self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                              {u"action": u"start",
                                                                               u"update": self.update},
                                                                              False)
            url = NSURL.URLWithString_(self.update[u"url"])
            request = NSURLRequest.requestWithURL_(url)
            NSURLConnection.connectionWithRequest_delegate_(request, self)
        else:
            self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                              {u"action": u"alldone"},
                                                                              False)
    
    def connection_didFailWithError_(self, connection, error):
        NSLog(u"%@ failed: %@", self.update[u"name"], error)
        self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                          {u"action": u"failed",
                                                                           u"update": self.update,
                                                                           u"error": error},
                                                                          False)
    
    def connection_didReceiveResponse_(self, connection, response):
        NSLog(u"%@ status code %d", self.update[u"name"], response.statusCode())
        self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                          {u"action": u"response",
                                                                           u"update": self.update,
                                                                           u"response": response},
                                                                          False)
    
    def connection_didReceiveData_(self, connection, data):
        self.bytesReceived += data.length()
        self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                          {u"action": u"data",
                                                                           u"update": self.update,
                                                                           u"bytes-received": self.bytesReceived},
                                                                          False)
    
    def connectionDidFinishLoading_(self, connection):
        NSLog(u"%@ finished downloading", self.update[u"name"])
        self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                          {u"action": u"checksumming",
                                                                           u"update": self.update},
                                                                          False)
        self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.selector,
                                                                          {u"action": u"checksum-ok",
                                                                           u"update": self.update},
                                                                          False)
        self.downloadNextUpdate()


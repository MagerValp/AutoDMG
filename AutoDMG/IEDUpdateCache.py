# -*- coding: utf-8 -*-
#
#  IEDUpdateCache.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-22.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
import os
import hashlib

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


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
        self.updateDir = os.path.join(url.path(), "AutoDMG", "Updates")
        if not os.path.exists(self.updateDir):
            try:
                os.makedirs(self.updateDir)
            except OSError as e:
                LogError("Failed to create %@: %@", self.updateDir, str(e))
        
        return self
    
    def initWithDelegate_(self, delegate):
        self = self.init()
        if self is None:
            return None
        
        self.delegate = delegate
        
        return self
    
    # Given a dictionary with sha1 hashes pointing to filenames, clean the
    # cache of unreferenced items, and create symlinks from the filenames to
    # the corresponding cache files.
    def pruneAndCreateSymlinks(self, symlinks):
        LogInfo("Pruning cache")
        
        self.symlinks = symlinks
        
        # Create a reverse dictionary and a set of filenames.
        names = dict()
        filenames = set()
        for sha1, name in symlinks.iteritems():
            names[name] = sha1
            filenames.add(name)
            filenames.add(sha1)
        
        for item in os.listdir(self.updateDir):
            try:
                itempath = os.path.join(self.updateDir, item)
                if item not in filenames:
                    LogInfo("Removing %@", item)
                    os.unlink(itempath)
            except OSError as e:
                LogWarning("Cache pruning of %@ failed: %@", item, str(e))
        for sha1 in symlinks.iterkeys():
            sha1Path = self.cachePath_(sha1)
            linkPath = self.updatePath_(sha1)
            name = os.path.basename(linkPath)
            if os.path.exists(sha1Path):
                if os.path.lexists(linkPath):
                    if os.readlink(linkPath) == sha1:
                        LogInfo("Found %@ -> %@", name, sha1)
                        continue
                    LogInfo("Removing stale link %@ -> %@", name, os.readlink(linkPath))
                    try:
                        os.unlink(linkPath)
                    except OSError as e:
                        LogWarning("Cache pruning of %@ failed: %@", name, str(c))
                        continue
                LogInfo("Creating %@ -> %@", name, sha1)
                os.symlink(sha1, linkPath)
            else:
                if os.path.lexists(linkPath):
                    LogInfo("Removing stale link %@ -> %@", name, os.readlink(linkPath))
                    try:
                        os.unlink(linkPath)
                    except OSError as e:
                        LogWarning("Cache pruning of %@ failed: %@", name, str(c))
            
    
    def isCached_(self, sha1):
        return os.path.exists(self.cachePath_(sha1))
    
    def updatePath_(self, sha1):
        return os.path.join(self.updateDir, self.symlinks[sha1])
    
    def cachePath_(self, sha1):
        return os.path.join(self.updateDir, sha1)
    
    def cacheTmpPath_(self, sha1):
        return os.path.join(self.updateDir, sha1 + ".part")
    
    
    
    # Download updates to cache.
    #
    # Delegate methods:
    #
    #     - (void)downloadAllDone
    #     - (void)downloadStarting:(NSDictionary *)update
    #     - (void)downloadGotData:(NSDictionary *)update bytesRead:(NSString *)bytes
    #     - (void)downloadSucceeded:(NSDictionary *)update
    #     - (void)downloadFailed:(NSDictionary *)update withError:(NSString *)message
    
    def downloadUpdates_(self, updates):
        self.updates = updates
        self.downloadNextUpdate()
    
    def stopDownload(self):
        self.connection.cancel()
        self.delegate.downloadStopped_(self.package)
        self.delegate.downloadAllDone()
    
    def downloadNextUpdate(self):
        if self.updates:
            self.package = self.updates.pop(0)
            self.bytesReceived = 0
            self.checksum = hashlib.sha1()
            self.delegate.downloadStarting_(self.package)
            
            path = self.cacheTmpPath_(self.package.sha1())
            if not NSFileManager.defaultManager().createFileAtPath_contents_attributes_(path, None, None):
                error = "Couldn't create temporary file at %s" % path
                self.delegate.downloadFailed_withError_(self.package, error)
                return
            self.fileHandle = NSFileHandle.fileHandleForWritingAtPath_(path)
            if not self.fileHandle:
                error = "Couldn't open %s for writing" % path
                self.delegate.downloadFailed_withError_(self.package, error)
                return
            
            url = NSURL.URLWithString_(self.package.url())
            request = NSURLRequest.requestWithURL_(url)
            self.connection = NSURLConnection.connectionWithRequest_delegate_(request, self)
            if self.connection:
                self.delegate.downloadStarted_(self.package)
        else:
            self.delegate.downloadAllDone()
    
    def connection_didFailWithError_(self, connection, error):
        LogError("%@ failed: %@", self.package.name(), error)
        self.delegate.downloadStopped_(self.package)
        self.fileHandle.closeFile()
        self.delegate.downloadFailed_withError_(self.package, error.localizedDescription())
        self.delegate.downloadAllDone()
    
    def connection_didReceiveResponse_(self, connection, response):
        LogDebug("%@ status code %d", self.package.name(), response.statusCode())
        if response.statusCode() >= 400:
            connection.cancel()
            self.fileHandle.closeFile()
            error = "%s failed with HTTP %d" % (self.package.name(), response.statusCode())
            self.delegate.downloadFailed_withError_(self.package, error)
            self.delegate.downloadAllDone()
    
    def connection_didReceiveData_(self, connection, data):
        try:
            self.fileHandle.writeData_(data)
        except BaseException as e:
            LogError("Write error: %@", str(e))
            connection.cancel()
            error = "Writing to %s failed: %s" % (self.cacheTmpPath_(self.package.sha1()), str(e))
            self.fileHandle.closeFile()
            self.delegate.downloadFailed_withError_(self.package, error)
            self.delegate.downloadAllDone()
            return
        self.checksum.update(data)
        self.bytesReceived += data.length()
        self.delegate.downloadGotData_bytesRead_(self.package, self.bytesReceived)
    
    def connectionDidFinishLoading_(self, connection):
        LogInfo("%@ finished downloading to %@", self.package.name(), self.cacheTmpPath_(self.package.sha1()))
        self.fileHandle.closeFile()
        self.delegate.downloadStopped_(self.package)
        if self.checksum.hexdigest() == self.package.sha1():
            try:
                os.rename(self.cacheTmpPath_(self.package.sha1()),
                          self.cachePath_(self.package.sha1()))
            except OSError as e:
                error = "Failed when moving download to %s: %s" % (self.cachePath_(self.package.sha1()), str(e))
                LogError(error)
                self.delegate.downloadFailed_withError_(self.package, error)
                return
            linkPath = self.updatePath_(self.package.sha1())
            try:
                os.symlink(self.package.sha1(), linkPath)
            except OSError as e:
                error = "Failed when creating link from %s to %s: %s" % (self.package.sha1(),
                                                                          linkPath,
                                                                          str(e))
                LogError(error)
                self.delegate.downloadFailed_withError_(self.package, error)
                return
            LogNotice("%@ added to cache with sha1 %@", self.package.name(), self.package.sha1())
            self.delegate.downloadSucceeded_(self.package)
            self.downloadNextUpdate()
        else:
            error = "Expected sha1 checksum %s but got %s" % (self.package.sha1().lower(), self.checksum.hexdigest().lower())
            LogError(error)
            self.delegate.downloadFailed_withError_(self.package, error)
            self.delegate.downloadAllDone()

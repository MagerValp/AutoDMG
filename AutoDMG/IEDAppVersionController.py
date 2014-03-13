#-*- coding: utf-8 -*-
#
#  IEDAppVersionController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright (c) Per Olofsson, 2013 University of Gothenburg. All rights reserved.
#

from Foundation import *
from objc import IBAction, IBOutlet

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
from IEDUtil import *


class IEDAppVersionController(NSObject):
    
    def awakeFromNib(self):
        self.defaults = NSUserDefaults.standardUserDefaults()
    
    @IBAction
    def checkForAppUpdate_(self, sender):
        self.checkForAppUpdateSilently_(False)
    
    def checkForAppUpdateSilently_(self, silently):
        self.checkSilently = silently
        # Create a buffer for data.
        self.plistData = NSMutableData.alloc().init()
        # Start download.
        url = NSURL.URLWithString_(self.defaults.stringForKey_(u"AppVersionURL"))
        request = NSURLRequest.requestWithURL_(url)
        self.connection = NSURLConnection.connectionWithRequest_delegate_(request, self)
        LogDebug(u"connection = %@", self.connection)
        if not self.connection:
            LogWarning(u"Connection to %@ failed", url)
    
    def logFailure_(self, message):
        LogError(u"Version check failed: %@", message)
        if not self.checkSilently:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(u"Version check failed")
            alert.setInformativeText_(message)
            alert.runModal()
        
    def connection_didFailWithError_(self, connection, error):
        self.logFailure_(error.localizedDescription())
    
    def connection_didReceiveResponse_(self, connection, response):
        if response.statusCode() != 200:
            connection.cancel()
            message = NSString.stringWithFormat_(u"Server returned HTTP %d",
                                                 response.statusCode())
            self.logFailure_(message)
    
    def connection_didReceiveData_(self, connection, data):
        self.plistData.appendData_(data)
    
    def connectionDidFinishLoading_(self, connection):
        LogDebug(u"Downloaded version check data with %d bytes", self.plistData.length())
        # Decode the plist.
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(self.plistData,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            self.logFailure_(error.localizedDescription())
            return
        
        # Save the time stamp.
        self.defaults.setObject_forKey_(NSDate.date(), u"LastAppVersionCheck")
        
        # Get latest version and build.
        latestDisplayVersion = plist[u"Version"]
        if latestDisplayVersion.count(u".") == 1:
            latestPaddedVersion = latestDisplayVersion + u".0"
        else:
            latestPaddedVersion = latestDisplayVersion
        latestBuild = plist[u"Build"]
        latestVersionBuild = u"%s.%s" % (latestPaddedVersion, latestBuild)
        LogNotice(u"Latest published version is AutoDMG v%@ build %@", latestDisplayVersion, latestBuild)
        
        if self.checkSilently:
            # Check if we've already notified the user about this version.
            if latestVersionBuild == self.defaults.stringForKey_(u"NotifiedAppVersion"):
                LogDebug(u"User has already been notified of this version.")
                return
        
        # Convert latest version into a tuple with (major, minor, rev, build).
        latestTuple = tuple(int(x.strip(u"ab")) for x in latestVersionBuild.split(u"."))
        
        # Get the current version and convert it to a tuple.
        displayVersion, build = IEDUtil.getAppVersion()
        if displayVersion.count(u".") == 1:
            paddedVersion = displayVersion + u".0"
        else:
            paddedVersion = displayVersion
        versionBuild = u"%s.%s" % (paddedVersion, build)
        currentTuple = tuple(int(x.strip(u"ab")) for x in versionBuild.split(u"."))
        
        # Compare and notify
        if latestTuple > currentTuple:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(u"A new version of AutoDMG is available")
            alert.setInformativeText_(u"AutoDMG v%s build %s is available for download." % (latestDisplayVersion, latestBuild))
            alert.addButtonWithTitle_(u"Download")
            alert.addButtonWithTitle_(u"Skip")
            alert.addButtonWithTitle_(u"Later")
            button = alert.runModal()
            if button == NSAlertFirstButtonReturn:
                url = NSURL.URLWithString_(plist[u"URL"])
                NSWorkspace.sharedWorkspace().openURL_(url)
            elif button == NSAlertSecondButtonReturn:
                self.defaults.setObject_forKey_(latestVersionBuild, u"NotifiedAppVersion")
        elif not self.checkSilently:
            alert = NSAlert.alloc().init()
            alert.setMessageText_(u"AutoDMG is up to date")
            if currentTuple > latestTuple:
                verString = u"bleeding edge"
            else:
                verString = u"current"
            alert.setInformativeText_(u"AutoDMG v%s build %s appears to be %s." % (displayVersion, build, verString))
            alert.runModal()


# -*- coding: utf-8 -*-
#
#  IEDAppVersionController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage, LogException
from IEDUtil import *


class IEDAppVersionController(NSObject):
    
    def awakeFromNib(self):
        self.defaults = NSUserDefaults.standardUserDefaults()
    
    @LogException
    @IBAction
    def checkForAppUpdate_(self, sender):
        self.checkForAppUpdateSilently_(False)
    
    def checkForAppUpdateSilently_(self, silently):
        self.checkSilently = silently
        # Create a buffer for data.
        self.plistData = NSMutableData.alloc().init()
        # Start download.
        osVer, osBuild = IEDUtil.readSystemVersion_("/")[1:3]
        appVer, appBuild = IEDUtil.getAppVersion()
        urlString = "%s?osVer=%s&osBuild=%s&appVer=%s&appBuild=%s" % (self.defaults.stringForKey_("AppVersionURL"),
                                                                       osVer,
                                                                       osBuild,
                                                                       appVer,
                                                                       appBuild)
        url = NSURL.URLWithString_(urlString)
        request = NSURLRequest.requestWithURL_(url)
        self.connection = NSURLConnection.connectionWithRequest_delegate_(request, self)
        LogDebug("connection = %@", self.connection)
        if not self.connection:
            LogWarning("Connection to %@ failed", url)
    
    def logFailure_(self, message):
        LogError("Version check failed: %@", message)
        if not self.checkSilently:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Version check failed")
            alert.setInformativeText_(message)
            alert.runModal()
        
    def connection_didFailWithError_(self, connection, error):
        self.logFailure_(error.localizedDescription())
    
    def connection_didReceiveResponse_(self, connection, response):
        if response.statusCode() != 200:
            connection.cancel()
            message = NSString.stringWithFormat_("Server returned HTTP %d",
                                                 response.statusCode())
            self.logFailure_(message)
    
    def connection_didReceiveData_(self, connection, data):
        self.plistData.appendData_(data)
    
    def connectionDidFinishLoading_(self, connection):
        LogDebug("Downloaded version check data with %d bytes", self.plistData.length())
        # Decode the plist.
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(self.plistData,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            self.logFailure_(error.localizedDescription())
            return
        
        # Save the time stamp.
        self.defaults.setObject_forKey_(NSDate.date(), "LastAppVersionCheck")
        
        # Get latest version and build.
        latestDisplayVersion = plist["Version"]
        if latestDisplayVersion.count(".") == 1:
            latestPaddedVersion = latestDisplayVersion + ".0"
        else:
            latestPaddedVersion = latestDisplayVersion
        latestBuild = plist["Build"]
        latestVersionBuild = "%s.%s" % (latestPaddedVersion, latestBuild)
        LogNotice("Latest published version is AutoDMG v%@ build %@", latestDisplayVersion, latestBuild)
        
        if self.checkSilently:
            # Check if we've already notified the user about this version.
            if latestVersionBuild == self.defaults.stringForKey_("NotifiedAppVersion"):
                LogDebug("User has already been notified of this version.")
                return
        
        # Convert latest version into a tuple with (major, minor, rev, build).
        latestTuple = IEDUtil.splitVersion(latestVersionBuild, strip="ab")
        
        # Get the current version and convert it to a tuple.
        displayVersion, build = IEDUtil.getAppVersion()
        if displayVersion.count(".") == 1:
            paddedVersion = displayVersion + ".0"
        else:
            paddedVersion = displayVersion
        versionBuild = "%s.%s" % (paddedVersion, build)
        currentTuple = IEDUtil.splitVersion(versionBuild, strip="ab")
        
        # Compare and notify
        if latestTuple > currentTuple:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("A new version of AutoDMG is available")
            alert.setInformativeText_("AutoDMG v%s build %s is available for download." % (latestDisplayVersion, latestBuild))
            alert.addButtonWithTitle_("Download")
            alert.addButtonWithTitle_("Skip")
            alert.addButtonWithTitle_("Later")
            button = alert.runModal()
            if button == NSAlertFirstButtonReturn:
                url = NSURL.URLWithString_(plist["URL"])
                NSWorkspace.sharedWorkspace().openURL_(url)
            elif button == NSAlertSecondButtonReturn:
                self.defaults.setObject_forKey_(latestVersionBuild, "NotifiedAppVersion")
        elif not self.checkSilently:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("AutoDMG is up to date")
            if currentTuple > latestTuple:
                verString = "bleeding edge"
            else:
                verString = "current"
            alert.setInformativeText_("AutoDMG v%s build %s appears to be %s." % (displayVersion, build, verString))
            alert.runModal()

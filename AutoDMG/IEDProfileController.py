# -*- coding: utf-8 -*-
#
#  IEDProfileController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-21.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from AppKit import *
from Foundation import *
from objc import IBOutlet

import os.path
from collections import defaultdict
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
from IEDUtil import *


class IEDProfileController(NSObject):
    """Keep track of update profiles, containing lists of the latest updates
    needed to build a fully updated OS X image."""
    
    profileUpdateWindow = IBOutlet()
    progressBar = IBOutlet()
    delegate = IBOutlet()
    
    def awakeFromNib(self):
        # Save the path to UpdateProfiles.plist in the user's application
        # support directory.
        fm = NSFileManager.defaultManager()
        url, error = fm.URLForDirectory_inDomain_appropriateForURL_create_error_(NSApplicationSupportDirectory,
                                                                                 NSUserDomainMask,
                                                                                 None,
                                                                                 True,
                                                                                 None)
        self.userUpdateProfilesPath = os.path.join(url.path(), "AutoDMG", "UpdateProfiles.plist")
        
        # Load UpdateProfiles from the application bundle.
        bundleUpdateProfilesPath = NSBundle.mainBundle().pathForResource_ofType_("UpdateProfiles", "plist")
        bundleUpdateProfiles = NSDictionary.dictionaryWithContentsOfFile_(bundleUpdateProfilesPath)
        
        latestProfiles = self.updateUsersProfilesIfNewer_(bundleUpdateProfiles)
        # Load the profiles.
        self.loadProfilesFromPlist_(latestProfiles)
    
    def setDelegate_(self, delegate):
        self.delegate = delegate
    
    def profileForVersion_Build_(self, version, build):
        """Return the update profile for a certain OS X version and build."""
        
        try:
            profile = self.profiles["%s-%s" % (version, build)]
            LogInfo("Update profile for %@ %@: %@", version, build, ", ".join(u["name"] for u in profile))
        except KeyError:
            profile = None
            LogNotice("No update profile for %@ %@", version, build)
        return profile
    
    def whyNoProfileForVersion_build_(self, whyVersion, whyBuild):
        """Given a version and build that doesn't have a profile, try to
        provide a helpful explanation as to why that might be."""
        
        # Check if it has been deprecated.
        LogDebug("Checking if %@ has been deprecated", whyBuild)
        try:
            replacement = self.deprecatedInstallerBuilds[whyBuild]
            version, _, build = replacement.partition("-")
            LogDebug("Installer deprecated by %@ %@", version, build)
            return "Installer deprecated by %s %s" % (version, build)
        except KeyError:
            pass
        
        whyVersionTuple = IEDUtil.splitVersion(whyVersion)
        whyMajor = whyVersionTuple[1]
        whyPoint = whyVersionTuple[2] if len(whyVersionTuple) > 2 else None
        
        buildsForVersion = defaultdict(set)
        supportedMajorVersions = set()
        supportedPointReleases = defaultdict(set)
        for versionBuild in self.profiles.iterkeys():
            version, _, build = versionBuild.partition("-")
            buildsForVersion[version].add(build)
            versionTuple = IEDUtil.splitVersion(version)
            major = versionTuple[1]
            supportedMajorVersions.add(major)
            point = versionTuple[2] if len(versionTuple) > 2 else 0
            supportedPointReleases[major].add(point)
        
        LogDebug("supported OS X versions: %@",
                 ", ".join("10.%d" % x for x in sorted(supportedMajorVersions)))
        LogDebug("supported point releases:")
        for major, pointReleases in supportedPointReleases.iteritems():
            LogDebug("    " + ", ".join("10.%d.%d" % (major, x) for x in sorted(pointReleases)))
        
        if whyMajor not in supportedMajorVersions:
            LogDebug("10.%d is not supported", whyMajor)
            return "10.%d is not supported" % whyMajor
        elif whyVersion in buildsForVersion:
            LogDebug("Unknown build %@", whyBuild)
            return "Unknown build %s" % whyBuild
        else:
            # It's a supported OS X version, but we don't have a profile for
            # this point release. Try to figure out if that's because it's too
            # old or too new.
            pointReleases = supportedPointReleases[whyMajor]
            oldestSupportedPointRelease = sorted(pointReleases)[0]
            newestSupportedPointRelease = sorted(pointReleases)[-1]
            if whyPoint < oldestSupportedPointRelease:
                LogDebug("Deprecated installer")
                return "Deprecated installer"
            elif whyPoint > newestSupportedPointRelease:
                # If it's newer than any known release, just assume that we're
                # behind on updates and that all is well.
                LogDebug("Installer newer than update profile")
                return "Installer newer than update profile"
            else:
                # Well this is awkward.
                LogDebug("Unknown %@ installer", whyVersion)
                return "Unknown %s installer" % whyVersion
    
    def updateUsersProfilesIfNewer_(self, plist):
        """Update the user's update profiles if plist is newer. Returns
           whichever was the newest."""
        
        LogDebug("Update user's profile if needed")
        
        # Load UpdateProfiles from the user's application support directory.
        userUpdateProfiles = NSDictionary.dictionaryWithContentsOfFile_(self.userUpdateProfilesPath)
        
        # Ensure profile in plist supports current OS.
        plistVersions = list(x.partition("-")[0] for x in plist["Profiles"].iterkeys())
        plistMajors = sorted(IEDUtil.splitVersion(x)[1] for x in plistVersions)
        osMajor = IEDUtil.hostVersionTuple()[1]
        plistSupportsOS = osMajor in plistMajors
        LogDebug("Profile %@ 10.%d",
                 "supports" if plistSupportsOS else "does not support",
                 osMajor)
        
        # If the plist is newer, update the user's.
        userIsEmpty = not userUpdateProfiles
        LogDebug("User profile %@", "is empty" if userIsEmpty else "is not empty")
        if userUpdateProfiles:
            userIsOlder = userUpdateProfiles["PublicationDate"].timeIntervalSinceDate_(plist["PublicationDate"]) < 0
            LogDebug("User profile %@", "is older" if userIsOlder else "is not older")
        else:
            userIsOlder = True
        if userIsEmpty or (userIsOlder and plistSupportsOS):
            LogDebug("Saving updated UpdateProfiles.plist")
            self.saveUsersProfiles_(plist)
            return plist
        else:
            LogDebug("Keeping previous UpdateProfiles.plist")
            return userUpdateProfiles
    
    def saveUsersProfiles_(self, plist):
        """Save UpdateProfiles.plist to application support."""
        
        LogInfo("Saving update profiles with PublicationDate %@", plist["PublicationDate"])
        if not plist.writeToFile_atomically_(self.userUpdateProfilesPath, False):
            LogError("Failed to write %@", self.userUpdateProfilesPath)
    
    def loadProfilesFromPlist_(self, plist):
        """Load UpdateProfiles from a plist dictionary."""
        
        LogInfo("Loading update profiles with PublicationDate %@", plist["PublicationDate"])
        
        self.profiles = dict()
        for name, updates in plist["Profiles"].iteritems():
            profile = list()
            for update in updates:
                profile.append(plist["Updates"][update])
            self.profiles[name] = profile
        
        self.publicationDate = plist["PublicationDate"]
        
        self.updatePaths = dict()
        for name, update in plist["Updates"].iteritems():
            filename, ext = os.path.splitext(os.path.basename(update["url"]))
            self.updatePaths[update["sha1"]] = "%s(%s)%s" % (filename, update["sha1"][:7], ext)
        
        self.deprecatedInstallerBuilds = dict()
        try:
            for replacement, builds in plist["DeprecatedInstallers"].iteritems():
                for build in builds:
                    self.deprecatedInstallerBuilds[build] = replacement
        except KeyError:
            LogWarning("No deprecated installers in profile")
        
        self.deprecatedOS = False
        try:
            hostVerMajor = IEDUtil.hostVersionTuple()[1]
            for osVerStr in plist["DeprecatedOSVersions"]:
                deprecatedVerMajor = IEDUtil.splitVersion(osVerStr)[1]
                if hostVerMajor <= deprecatedVerMajor:
                    self.deprecatedOS = True
                    LogWarning("%@ is no longer being updated by Apple", osVerStr)
                    break
        except KeyError:
            LogWarning("No deprecated OS versions in profile")
        
        if self.delegate:
            self.delegate.profilesUpdated()
    
    
    
    # Update profiles.
    
    def updateFromURL_(self, url):
        """Download the latest UpdateProfiles.plist."""
        
        LogDebug("updateFromURL:%@", url)
        
        if self.profileUpdateWindow:
            # Show the progress window.
            self.progressBar.setIndeterminate_(True)
            self.progressBar.startAnimation_(self)
            self.profileUpdateWindow.makeKeyAndOrderFront_(self)
        
        # Create a buffer for data.
        self.profileUpdateData = NSMutableData.alloc().init()
        # Start download.
        request = NSURLRequest.requestWithURL_(url)
        self.connection = NSURLConnection.connectionWithRequest_delegate_(request, self)
        LogDebug("connection = %@", self.connection)
        if not self.connection:
            LogWarning("Connection to %@ failed", url)
            if self.profileUpdateWindow:
                self.profileUpdateWindow.orderOut_(self)
            self.delegate.profileUpdateFailed_(error)
    
    def connection_didFailWithError_(self, connection, error):
        LogError("Profile update failed: %@", error)
        if self.profileUpdateWindow:
            self.profileUpdateWindow.orderOut_(self)
        self.delegate.profileUpdateFailed_(error)
        self.delegate.profileUpdateAllDone()
    
    def connection_didReceiveResponse_(self, connection, response):
        LogDebug("%@ status code %d", connection, response.statusCode())
        if response.expectedContentLength() == NSURLResponseUnknownLength:
            LogDebug("unknown response length")
        else:
            LogDebug("Downloading profile with %d bytes", response.expectedContentLength())
            if self.profileUpdateWindow:
                self.progressBar.setMaxValue_(float(response.expectedContentLength()))
                self.progressBar.setDoubleValue_(float(response.expectedContentLength()))
                self.progressBar.setIndeterminate_(False)
    
    def connection_didReceiveData_(self, connection, data):
        self.profileUpdateData.appendData_(data)
        if self.profileUpdateWindow:
            self.progressBar.setDoubleValue_(float(self.profileUpdateData.length()))
    
    def connectionDidFinishLoading_(self, connection):
        LogDebug("Downloaded profile with %d bytes", self.profileUpdateData.length())
        if self.profileUpdateWindow:
            # Hide the progress window.
            self.profileUpdateWindow.orderOut_(self)
        # Decode the plist.
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(self.profileUpdateData,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            self.delegate.profileUpdateFailed_(error)
            return
        LogNotice("Downloaded update profiles with PublicationDate %@", plist["PublicationDate"])
        # Update the user's profiles if it's newer.
        latestProfiles = self.updateUsersProfilesIfNewer_(plist)
        # Load the latest profiles.
        self.loadProfilesFromPlist_(latestProfiles)
        # Notify delegate.
        self.delegate.profileUpdateSucceeded_(latestProfiles["PublicationDate"])
        self.delegate.profileUpdateAllDone()
    
    def cancelUpdateDownload(self):
        LogInfo("User canceled profile update")
        self.connection.cancel()
        self.profileUpdateWindow.orderOut_(self)

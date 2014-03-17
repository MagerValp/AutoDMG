#-*- coding: utf-8 -*-
#
#  IEDProfileController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-21.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from AppKit import *
from Foundation import *
from objc import IBOutlet

import os.path
from collections import defaultdict
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


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
        self.userUpdateProfilesPath = os.path.join(url.path(), u"AutoDMG", u"UpdateProfiles.plist")
        
        # Load UpdateProfiles from the application bundle.
        bundleUpdateProfilesPath = NSBundle.mainBundle().pathForResource_ofType_(u"UpdateProfiles", u"plist")
        bundleUpdateProfiles = NSDictionary.dictionaryWithContentsOfFile_(bundleUpdateProfilesPath)
        
        latestProfiles = self.updateUsersProfilesIfNewer_(bundleUpdateProfiles)
        # Load the profiles.
        self.loadProfilesFromPlist_(latestProfiles)
    
    def setDelegate_(self, delegate):
        self.delegate = delegate
    
    def profileForVersion_Build_(self, version, build):
        """Return the update profile for a certain OS X version and build."""
        
        try:
            profile = self.profiles[u"%s-%s" % (version, build)]
            LogInfo(u"Update profile for %@ %@: %@", version, build, u", ".join(u[u"name"] for u in profile))
        except KeyError:
            profile = None
            LogNotice(u"No update profile for %@ %@", version, build)
        return profile
    
    def whyNoProfileForVersion_build_(self, whyVersion, whyBuild):
        """Given a version and build that doesn't have a profile, try to
        provide a helpful explanation as to why that might be."""
        
        # Check if it has been deprecated.
        try:
            replacement = self.deprecatedInstallerBuilds[whyBuild]
            version, _, build = replacement.partition(u"-")
            return u"Installer deprecated by %s %s" % (version, build)
        except KeyError:
            pass
        
        whyVersionTuple = tuple(int(x) for x in whyVersion.split(u"."))
        whyMajor = whyVersionTuple[1]
        whyPoint = whyVersionTuple[2] if len(whyVersionTuple) > 2 else None
        
        buildsForVersion = defaultdict(set)
        supportedMajorVersions = set()
        supportedPointReleases = defaultdict(set)
        for versionBuild in self.profiles.keys():
            version , _, build = versionBuild.partition(u"-")
            buildsForVersion[version].add(build)
            versionTuple = tuple(int(x) for x in version.split(u"."))
            major = versionTuple[1]
            supportedMajorVersions.add(major)
            point = versionTuple[2] if len(versionTuple) > 2 else None
            supportedPointReleases[major].add(point)
        
        if whyMajor not in supportedMajorVersions:
            return "10.%d is not supported" % whyMajor
        elif whyVersion in buildsForVersion:
            return u"Unknown build %s" % whyBuild
        else:
            # It's a supported OS X version, but we don't have a profile for
            # this point release. Try to figure out if that's because it's too
            # old or too new.
            pointReleases = supportedPointReleases[whyMajor]
            oldestSupportedPointRelease = sorted(pointReleases)[0]
            newestSupportedPointRelease = sorted(pointReleases)[-1]
            if whyPoint < oldestSupportedPointRelease:
                return u"Deprecated installer"
            elif whyPoint > newestSupportedPointRelease:
                # If it's newer than any known release, just assume that we're
                # behind on updates and that all is well.
                return None
            else:
                # Well this is awkward.
                return u"Deprecated installer"
    
    def updateUsersProfilesIfNewer_(self, plist):
        """Update the user's update profiles if plist is newer. Returns
           whichever was the newest."""
        
        # Load UpdateProfiles from the user's application support directory.
        userUpdateProfiles = NSDictionary.dictionaryWithContentsOfFile_(self.userUpdateProfilesPath)
        
        # If the bundle's plist is newer, update the user's.
        if (not userUpdateProfiles) or (userUpdateProfiles[u"PublicationDate"].timeIntervalSinceDate_(plist[u"PublicationDate"]) < 0):
            LogDebug(u"Saving updated UpdateProfiles.plist")
            self.saveUsersProfiles_(plist)
            return plist
        else:
            return userUpdateProfiles
    
    def saveUsersProfiles_(self, plist):
        """Save UpdateProfiles.plist to application support."""
        
        LogInfo(u"Saving update profiles with PublicationDate %@", plist[u"PublicationDate"])
        if not plist.writeToFile_atomically_(self.userUpdateProfilesPath, False):
            LogError(u"Failed to write %@", self.userUpdateProfilesPath)
    
    def loadProfilesFromPlist_(self, plist):
        """Load UpdateProfiles from a plist dictionary."""
        
        LogInfo(u"Loading update profiles with PublicationDate %@", plist[u"PublicationDate"])
        self.profiles = dict()
        for name, updates in plist[u"Profiles"].iteritems():
            profile = list()
            for update in updates:
                profile.append(plist[u"Updates"][update])
            self.profiles[name] = profile
        self.publicationDate = plist[u"PublicationDate"]
        self.updatePaths = dict()
        for name, update in plist[u"Updates"].iteritems():
            self.updatePaths[update[u"sha1"]] = os.path.basename(update[u"url"])
        self.deprecatedInstallerBuilds = dict()
        try:
            for replacement, builds in plist[u"DeprecatedInstallers"].iteritems():
                for build in builds:
                    self.deprecatedInstallerBuilds[build] = replacement
        except KeyError:
            LogWarning(u"No deprecated installers")
        if self.delegate:
            self.delegate.profilesUpdated()
    
    
    
    # Update profiles.
    
    def updateFromURL_(self, url):
        """Download the latest UpdateProfiles.plist."""
        
        LogDebug(u"updateFromURL:%@", url)
        
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
        LogDebug(u"connection = %@", self.connection)
        if not self.connection:
            LogWarning(u"Connection to %@ failed", url)
            if self.profileUpdateWindow:
                self.profileUpdateWindow.orderOut_(self)
            self.delegate.profileUpdateFailed_(error)
    
    def connection_didFailWithError_(self, connection, error):
        LogError(u"Profile update failed: %@", error)
        if self.profileUpdateWindow:
            self.profileUpdateWindow.orderOut_(self)
        self.delegate.profileUpdateFailed_(error)
        self.delegate.profileUpdateAllDone()
    
    def connection_didReceiveResponse_(self, connection, response):
        LogDebug(u"%@ status code %d", connection, response.statusCode())
        if response.expectedContentLength() == NSURLResponseUnknownLength:
            LogDebug(u"unknown response length")
        else:
            LogDebug(u"Downloading profile with %d bytes", response.expectedContentLength())
            if self.profileUpdateWindow:
                self.progressBar.setMaxValue_(float(response.expectedContentLength()))
                self.progressBar.setDoubleValue_(float(response.expectedContentLength()))
                self.progressBar.setIndeterminate_(False)
    
    def connection_didReceiveData_(self, connection, data):
        self.profileUpdateData.appendData_(data)
        if self.profileUpdateWindow:
            self.progressBar.setDoubleValue_(float(self.profileUpdateData.length()))
    
    def connectionDidFinishLoading_(self, connection):
        LogDebug(u"Downloaded profile with %d bytes", self.profileUpdateData.length())
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
        LogNotice(u"Downloaded update profiles with PublicationDate %@", plist[u"PublicationDate"])
        # Update the user's profiles if it's newer.
        latestProfiles = self.updateUsersProfilesIfNewer_(plist)
        # Load the latest profiles.
        self.loadProfilesFromPlist_(latestProfiles)
        # Notify delegate.
        self.delegate.profileUpdateSucceeded_(latestProfiles[u"PublicationDate"])
        self.delegate.profileUpdateAllDone()
    
    def cancelUpdateDownload(self):
        LogInfo(u"User canceled profile update")
        self.connection.cancel()
        self.profileUpdateWindow.orderOut_(self)



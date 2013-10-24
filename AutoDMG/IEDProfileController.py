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


class IEDProfileController(NSObject):
    """Singleton class to keep track of update profiles, containing lists of
       the latest updates needed to build a fully updated OS X image."""
    
    _instance = None
    
    profileUpdateWindow = IBOutlet()
    progressBar = IBOutlet()
    
    def init(self):
        # Return singleton instance if it's already initialized.
        if IEDProfileController._instance:
            return IEDProfileController._instance
        
        # Otherwise we initialize a new instance.
        self = super(IEDProfileController, self).init()
        if self is None:
            return None
        IEDProfileController._instance = self
        
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
        
        return self
    
    def profileForVersion_Build_(self, version, build):
        """Return the update profile for a certain OS X version and build."""
        
        try:
            return self.profiles[u"%s-%s" % (version, build)]
        except KeyError:
            return None
    
    def updateUsersProfilesIfNewer_(self, plist):
        """Update the user's update profiles if plist is newer. Returns
           whichever was the newest."""
        
        # Load UpdateProfiles from the user's application support directory.
        userUpdateProfiles = NSDictionary.dictionaryWithContentsOfFile_(self.userUpdateProfilesPath)
        
        # If the bundle's plist is newer, update the user's.
        if (not userUpdateProfiles) or (userUpdateProfiles[u"PublicationDate"].timeIntervalSinceDate_(plist[u"PublicationDate"]) < 0):
            self.saveUsersProfiles_(plist)
            userUpdateProfiles = plist
        
        return userUpdateProfiles
    
    def saveUsersProfiles_(self, plist):
        """Save UpdateProfiles.plist to application support."""
        
        if not plist.writeToFile_atomically_(self.userUpdateProfilesPath, False):
            NSLog(u"Failed to write %@", self.userUpdateProfilesPath)
    
    def loadProfilesFromPlist_(self, plist):
        """Load UpdateProfiles from a plist dictionary."""
        
        self.profiles = dict()
        for name, updates in plist[u"Profiles"].iteritems():
            profile = list()
            for update in updates:
                profile.append(plist[u"Updates"][update])
            self.profiles[name] = profile
        self.publicationDate = plist[u"PublicationDate"]
    
    def updateFromURL_withTarget_selector_(self, url, target, selector):
        """Download the latest update profiles asynchronously and notify
           target with the result."""
        
        self.profileUpdateWindow.makeKeyAndOrderFront_(self)
        self.progressBar.startAnimation_(self)
        self.performSelectorInBackground_withObject_(self.updateInBackground_, [url, target, selector])
    
    # Continue in background thread.
    def updateInBackground_(self, args):
        url, target, selector = args
        request = NSURLRequest.requestWithURL_(url)
        data, response, error = NSURLConnection.sendSynchronousRequest_returningResponse_error_(request, None, None)
        self.profileUpdateWindow.orderOut_(self)
        if not data:
            message = u"Failed to download %s: %s" % (url.absoluteString(), error.localizedDescription())
            self.failUpdate_withTarget_selector_(message, target, selector)
            return
        if response.statusCode() != 200:
            self.failUpdate_withTarget_selector_(u"Update server responded with code %d.", response.statusCode(), target, selector)
            return
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(data,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            self.failUpdate_withTarget_selector_(u"Couldn't decode update data.", target, selector)
            return
        NSLog(u"Downloaded update profiles with PublicationDate = %@", plist[u"PublicationDate"])
        latestProfiles = self.updateUsersProfilesIfNewer_(plist)
        self.loadProfilesFromPlist_(latestProfiles)
        dateFormatter = NSDateFormatter.alloc().init()
        timeZone = NSTimeZone.timeZoneWithName_(u"UTC")
        dateFormatter.setTimeZone_(timeZone)
        dateFormatter.setDateFormat_(u"yyyy-MM-dd HH:mm:ss")
        dateString = dateFormatter.stringFromDate_(latestProfiles[u"PublicationDate"])
        message = u"Using update profiles from %s UTC" % dateString
        self.succeedUpdate_WithTarget_selector_(message, target, selector)
    
    def failUpdate_withTarget_selector_(self, error, target, selector):
        """Notify target of a failed update."""
        
        NSLog(u"Profile update failed: %@", error)
        if target:
            target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                         {u"success": False,
                                                                          u"error-message": error},
                                                                         False)
    
    def succeedUpdate_WithTarget_selector_(self, message, target, selector):
        """Notify target of a successful update."""
        
        if target:
            target.performSelectorOnMainThread_withObject_waitUntilDone_(selector,
                                                                         {u"success": True,
                                                                          u"message": message},
                                                                         False)


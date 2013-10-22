#-*- coding: utf-8 -*-
#
#  IEDProfileController.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-21.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *


class IEDProfileController(NSObject):
    """Class to keep track of update profiles, containing the latest updates
       needed to build a fully updated OS X image."""
    
    def init(self):
        self = super(IEDProfileController, self).init()
        if self is None:
            return None
        
        supp1085 = {
            u"name": u"OS X Mountain Lion 10.8.5 Supplemental Update",
            u"url": u"http://support.apple.com/downloads/DL1686/en_US/OSXUpd10.8.5Supp.dmg",
            u"sha1": u"18636c06f0db5b326752628fb7a2dfa3ce077ae1",
            u"size": 19648899,
        }
        itunes = {
            u"name": u"iTunes 11.1.1",
            u"url": u"https://secure-appldnld.apple.com/iTunes11/091-9970.20131002.r3miz/iTunes11.1.1.dmg",
            u"sha1": u"66b75a92d234affaed19484810d8dc53ed4608dd",
            u"size": 225609082,
        }
        java = {
            u"name": u"Java for OS X 2013-005",
            u"url": u"http://support.apple.com/downloads/DL1572/en_US/JavaForOSX2013-05.dmg",
            u"sha1": u"ce78f9a916b91ec408c933bd0bde5973ca8a2dc4",
            u"size": 67090041,
        }
        airportutil = {
            u"name": u"AirPort Utility 6.3.1 for Mac",
            u"url": u"http://support.apple.com/downloads/DL1664/en_US/AirPortUtility6.3.1.dmg",
            u"sha1": u"7cb449454ef5c2cf478a2a5394f652a9705c9481",
            u"size": 22480138,
        }
        self.profiles = {
            u"10.8.5-12F37": [
                supp1085,
                itunes,
                airportutil,
            ],
            u"10.8.5-12F45": [
                itunes,
                airportutil,
            ],
            u"10.9-13A598": [
                itunes,
                airportutil,
            ],
            u"10.9-13A603": [
                itunes,
                airportutil,
            ],
        }
        
        return self
    
    def updateFromURL_withTarget_selector_(self, url, target, selector):
        """Download the latest profiles."""
        
        NSLog(u"updateFromURL:withTarget:selector: unimplemented")
    
    def profileForVersion_Build_(self, version, build):
        """Return the update profile for a certain OS X version and build."""
        
        try:
            return self.profiles[u"%s-%s" % (version, build)]
        except KeyError:
            return None


# -*- coding: utf-8 -*-
#
#  IEDPackage.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-26.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *


class IEDPackage(NSObject):

    def init(self):
        self = super(IEDPackage, self).init()
        if self is None:
            return None
        
        self._name = None
        self._path = None
        self._size = None
        self._url = None
        self._image = None
        self._sha1 = None
        
        return self
    
    def name(self):
        return self._name
    
    def setName_(self, name):
        self._name = name
    
    def path(self):
        return self._path
    
    def setPath_(self, path):
        self._path = path
    
    def size(self):
        return self._size
    
    def setSize_(self, size):
        self._size = size
    
    def url(self):
        return self._url
    
    def setUrl_(self, url):
        self._url = url
    
    def image(self):
        return self._image
    
    def setImage_(self, image):
        self._image = image
    
    def sha1(self):
        return self._sha1
    
    def setSha1_(self, sha1):
        self._sha1 = sha1

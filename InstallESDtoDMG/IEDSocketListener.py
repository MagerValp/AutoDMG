#-*- coding: utf-8 -*-
#
#  IEDSocketListener.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-10-10.
#  Copyright (c) 2013 University of Gothenburg. All rights reserved.
#

from Foundation import *
import os
import socket


IEDSL_MAX_MSG_SIZE = 4096


class IEDSocketListener(NSObject):
    
    target = None
    action = None
    watchThread = None
    
    def listenOnSocketInDir_withName_target_action_(self, sockdir, name, target, action):
        socketPath = NSString.stringWithFormat_(u"%@/%@.%@", sockdir, name, os.urandom(8).encode("hex"))
        self.target = target
        self.action = action
        self.watchThread = NSThread.alloc().initWithTarget_selector_object_(self, u"listenInBackground:", socketPath)
        self.watchThread.start()
        return socketPath
    
    def stopListening(self):
        self.watchThread.cancel()
    
    def listenInBackground_(self, socketPath):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.bind(socketPath)
        except socket.error as e:
            NSLog(u"Error creating datagram socket at %@: %@", socketPath, unicode(e))
            return
        
        while True:
            msg = sock.recv(IEDSL_MAX_MSG_SIZE, socket.MSG_WAITALL)
            if not msg:
                continue
            msgData = NSData.dataWithBytes_length_(msg, len(msg))
            plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(msgData,
                                                                                                          NSPropertyListImmutable,
                                                                                                          None,
                                                                                                          None)
            if not plist:
                NSLog(u"Error decoding plist: %@", error)
                continue
            if self.target.respondsToSelector_(self.action):
                self.target.performSelectorOnMainThread_withObject_waitUntilDone_(self.action, plist, NO)

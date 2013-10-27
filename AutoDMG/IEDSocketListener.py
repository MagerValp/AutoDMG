#-*- coding: utf-8 -*-
#
#  IEDSocketListener.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-10-10.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
import os
import socket

from IEDLog import *


IEDSL_MAX_MSG_SIZE = 4096


class IEDSocketListener(NSObject):
    """Open a unix domain datagram socket and wait for messages encoded as
    plists, which are decoded and passed on to the delegate."""
    
    def listenOnSocket_withDelegate_(self, path, delegate):
        self.socketPath = NSString.stringWithFormat_(u"%@.%@", path, os.urandom(8).encode("hex"))
        LogDebug(u"Creating socket at %@", self.socketPath)
        self.delegate = delegate
        self.watchThread = NSThread.alloc().initWithTarget_selector_object_(self, u"listenInBackground:", None)
        self.watchThread.start()
        return self.socketPath
    
    def stopListening(self):
        LogDebug(u"stopListening")
        self.watchThread.cancel()
        try:
            os.unlink(self.socketPath)
        except BaseException as e:
            LogWarning(u"Couldn't remove listener socket %@: %@", self.socketPath, unicode(e))
    
    def listenInBackground_(self, ignored):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.bind(self.socketPath)
        except socket.error as e:
            LogError(u"Error creating datagram socket at %@: %@", self.socketPath, unicode(e))
            return
        
        LogDebug(u"Listening to socket in background thread")
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
                LogError(u"Error decoding plist: %@", error)
                continue
            LogDebug(u"Received message on socket: %@", plist)
            if self.delegate.respondsToSelector_(u"socketReceivedMessage:"):
                self.delegate.performSelectorOnMainThread_withObject_waitUntilDone_(u"socketReceivedMessage:", plist, NO)

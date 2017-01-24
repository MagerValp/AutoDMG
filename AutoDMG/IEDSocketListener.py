# -*- coding: utf-8 -*-
#
#  IEDSocketListener.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-10.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *
import os
import socket
import glob

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


IEDSL_MAX_MSG_SIZE = 32768
IEDSL_MAX_MSG_COUNT = 2


class IEDSocketListener(NSObject):
    """Open a unix domain datagram socket and wait for messages encoded as
    plists, which are decoded and passed on to the delegate."""
    
    def listenOnSocket_withDelegate_(self, path, delegate):
        for oldsocket in glob.glob("%s.*" % path):
            LogDebug("Removing old socket %@", oldsocket)
            try:
                os.unlink(oldsocket)
            except:
                pass
        self.socketPath = NSString.stringWithFormat_("%@.%@", path, os.urandom(8).encode("hex"))
        LogDebug("Creating socket at %@", self.socketPath)
        self.delegate = delegate
        self.watchThread = NSThread.alloc().initWithTarget_selector_object_(self, "listenInBackground:", None)
        self.watchThread.start()
        return self.socketPath
    
    def stopListening(self):
        LogDebug("stopListening")
        self.watchThread.cancel()
        try:
            os.unlink(self.socketPath)
        except BaseException as e:
            LogWarning("Couldn't remove listener socket %@: %@", self.socketPath, str(e))
    
    def listenInBackground_(self, ignored):
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, (IEDSL_MAX_MSG_SIZE + 16) * IEDSL_MAX_MSG_COUNT)
            sock.bind(self.socketPath)
        except socket.error as e:
            LogError("Error creating datagram socket at %@: %@", self.socketPath, str(e))
            return
        
        LogDebug("Listening to socket in background thread")
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
                LogError("Error decoding plist: %@", error)
                continue
            if self.delegate.respondsToSelector_("socketReceivedMessage:"):
                self.delegate.performSelectorOnMainThread_withObject_waitUntilDone_("socketReceivedMessage:", plist, NO)

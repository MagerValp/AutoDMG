#!/usr/bin/python

#-*- coding: utf-8 -*-
#
#  progresswatcher.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-26.
#  Copyright (c) 2013 University of Gothenburg. All rights reserved.
#


import os
import sys
import optparse
import socket
from Foundation import *


class ProgressWatcher(NSObject):
    
    outputBuffer = None
    isTaskRunning = False
    sock = None
    sockPath = None
    
    def watchTask_withSocket_(self, args, sockPath):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sockPath = sockPath
        
        nc = NSNotificationCenter.defaultCenter()
        
        self.isTaskRunning = True
        task = NSTask.alloc().init()
        
        outpipe = NSPipe.alloc().init()
        stdoutHandle = outpipe.fileHandleForReading()
        task.setStandardOutput_(outpipe)
        self.outputBuffer = u""
        
        task.setLaunchPath_(args[0])
        task.setArguments_(args[1:])
        
        nc.addObserver_selector_name_object_(self,
                                             u"notifyProgressData:",
                                             NSFileHandleReadCompletionNotification,
                                             stdoutHandle)
        stdoutHandle.readInBackgroundAndNotify()
        
        nc.addObserver_selector_name_object_(self,
                                             u"notifyProgressTermination:",
                                             NSTaskDidTerminateNotification,
                                             task)
        task.launch()
    
    def shouldKeepRunning(self):
        return self.isTaskRunning
    
    def notifyProgressTermination_(self, notification):
        task = notification.object()
        if task.terminationStatus() == 0:
            pass
        self.postNotification_({u"action": u"task_done", u"termination_status": task.terminationStatus()})
        self.isTaskRunning = False
    
    def notifyProgressData_(self, notification):
        data = notification.userInfo()[NSFileHandleNotificationDataItem]
        if data.length():
            string = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if string:
                self.appendOutput_(string)
            else:
                NSLog(u"Couldn't decode %@ as UTF-8", data)
            notification.object().readInBackgroundAndNotify()
    
    def appendOutput_(self, string):
        self.outputBuffer += string
        while "\n" in self.outputBuffer:
            line, newline, self.outputBuffer = self.outputBuffer.partition("\n")
            self.parseProgress_(line)
    
    def parseProgress_(self, string):
        # Wrap progress parsing so app doesn't crash from bad input.
        try:
            if string.startswith(u"installer:"):
                self.parseInstallerProgress_(string[10:])
            elif string.startswith(u"IED:"):
                self.parseIEDProgress_(string[4:])
            else:
                NSLog(u"(Ignoring progress %@)", string)
        except BaseException as e:
            NSLog(u"Progress parsing failed with exception: %s" % e)
    
    def parseInstallerProgress_(self, string):
        if string.startswith(u"%"):
            progress = float(string[1:])
            self.postNotification_({u"action": u"update_progressbar", u"percent": progress})
        elif string.startswith(u"PHASE:"):
            message = string[6:]
            self.postNotification_({u"action": u"update_message", u"message": message})
        elif string.startswith(u"STATUS:"):
            pass
        else:
            pass
            #NSLog(u"(Ignoring installer progress %@)", string)
    
    def parseIEDProgress_(self, string):
        if string.startswith(u"%"):
            progress = float(string[1:])
            if progress < 0:
                progress = None
            self.postNotification_({u"action": u"update_progressbar", u"percent": progress})
        elif string.startswith(u"MSG:"):
            message = string[4:]
            self.postNotification_({u"action": u"update_message", u"message": message})
        elif string.startswith(u"SUCCESS:"):
            message = string[8:]
            self.postNotification_({u"action": u"notify_success", u"message": message})
        elif string.startswith(u"FAILURE:"):
            message = string[8:]
            self.postNotification_({u"action": u"notify_failure", u"message": message})
        else:
            NSLog(u"(Unknown IED progress %@)", string)
    
    def postNotification_(self, msgDict):
        msg, error = NSPropertyListSerialization.dataWithPropertyList_format_options_error_(msgDict,
                                                                                            NSPropertyListBinaryFormat_v1_0,
                                                                                            0,
                                                                                            None)
        if not msg:
            if error:
                NSLog(u"plist encoding failed: %@", error)
            return
        try:
            self.sock.sendto(msg, self.sockPath)
        except socket.error, e:
            NSLog(u"Socket at %@ failed: %@", self.sockPath, unicode(e))
    

def main(argv):
    p = optparse.OptionParser()
    p.set_usage("""Usage: %prog [options] socket source destination""")
    p.add_option("-v", "--verbose", action="store_true", help="Verbose output.")
    p.add_option("-d", "--cd", help="Set current directory.")
    options, argv = p.parse_args(argv)
    if len(argv) != 4:
        print >>sys.stderr, p.get_usage()
        return 1
    
    sockPath = argv[1]
    sourcePath = argv[2].decode("utf-8")
    destinationPath = argv[3].decode("utf-8")
    
    if options.cd:
        os.chdir(options.cd)
    
    args = [u"./installesdtodmg.sh", sourcePath, destinationPath]
    NSLog(u'Launching task "%@"', u'" "'.join(args))
    
    pw = ProgressWatcher.alloc().init()
    pw.watchTask_withSocket_(args, sockPath)
    
    runLoop = NSRunLoop.currentRunLoop()
    while pw.shouldKeepRunning():
        runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.distantFuture())
    
    NSLog(u"Task terminated, exiting")
    
    return 0
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))
    

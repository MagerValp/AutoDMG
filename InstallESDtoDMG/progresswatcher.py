#!/usr/bin/python

#-*- coding: utf-8 -*-
#
#  progresswatcher.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-26.
#  Copyright (c) 2013 University of Gothenburg. All rights reserved.
#


import sys
import optparse
from Foundation import *


class ProgressWatcher(NSObject):
    
    outputBuffer = None
    dnc = None
    isTaskRunning = False
    
    def watchTask_(self, args):
        self.dnc = NSDistributedNotificationCenter.defaultCenter()
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
                self.parseInstallerProgress_(string)
            else:
                NSLog(u"(Ignoring progress %@)", string)
        except BaseException as e:
            NSLog(u"Progress parsing failed with exception: %s" % e)
    
    def parseInstallerProgress_(self, string):
        string = string[10:]
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
    
    def postNotification_(self, attributes):
        self.dnc.postNotificationName_object_userInfo_(u"se.gu.it.IEDUpdate", u"progress", attributes)
    

def main(argv):
    p = optparse.OptionParser()
    p.set_usage("""Usage: %prog [options]""")
    p.add_option("-v", "--verbose", action="store_true",
                 help="Verbose output.")
    options, argv = p.parse_args(argv)
    if len(argv) != 1:
        print >>sys.stderr, p.get_usage()
        return 1
    
    pw = ProgressWatcher.alloc().init()
    pw.watchTask_([u"./test.sh"])
    
    runLoop = NSRunLoop.currentRunLoop()
    while pw.shouldKeepRunning():
        runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.distantFuture())
    
    return 0
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))
    

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
    
    def watchTask_(self, args):
        nc = NSNotificationCenter.defaultCenter()
        
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
        NSLog(u"launching")
        task.launch()
    
    def notifyProgressTermination_(self, notification):
        NSLog(u"terminated")
        task = notification.object()
        if task.terminationStatus() == 0:
            pass
        #self.stopTaskProgress()
    
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
                pass
        except BaseException as e:
            NSLog(u"Progress parsing failed with exception: %s" % e)
    
    def parseInstallerProgress_(self, string):
        NSLog(u"parseInstallerProgress:%@", string[10:])
        string = string[10:]
        if string.startswith(u"%"):
            progress = float(string[1:])
            NSLog(u"progress %f", progress)
            self.notifyProgress_(progress)
    
    def notifyProgress_(self, progress):
        NSLog(u"Sending progress %f", progress)
        dnc = NSDistributedNotificationCenter.defaultCenter()
        dnc.postNotificationName_object_userInfo_(u"se.gu.it.IEDUpdate", u"progress", {u"percent": progress})
    

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
    runLoop.run()
    
    return 0
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))
    

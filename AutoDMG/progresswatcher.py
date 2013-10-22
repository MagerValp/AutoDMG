#!/usr/bin/python

#-*- coding: utf-8 -*-
#
#  progresswatcher.py
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-26.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#


import os
import sys
import argparse
import socket
from Foundation import *


class ProgressWatcher(NSObject):
    
    def watchTask_socket_mode_(self, args, sockPath, mode):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sockPath = sockPath
        
        nc = NSNotificationCenter.defaultCenter()
        
        self.isTaskRunning = True
        task = NSTask.alloc().init()
        
        outpipe = NSPipe.alloc().init()
        stdoutHandle = outpipe.fileHandleForReading()
        task.setStandardOutput_(outpipe)
        
        task.setLaunchPath_(args[0])
        task.setArguments_(args[1:])
        
        if mode == u"asr":
            progressHandler = u"notifyAsrProgressData:"
            self.asrProgressActive = False
        elif mode == u"ied":
            progressHandler = u"notifyIEDProgressData:"
            self.outputBuffer = u""
        nc.addObserver_selector_name_object_(self,
                                             progressHandler,
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
    
    def notifyAsrProgressData_(self, notification):
        data = notification.userInfo()[NSFileHandleNotificationDataItem]
        if data.length():
            string = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if string == u"Block checksum: ":
                self.asrPercent = 0.0
                self.asrProgressActive = True
            elif self.asrProgressActive:
                while string and self.asrProgressActive:
                    if string.startswith(u"."):
                        while string.startswith(u"."):
                            string = string[1:]
                            self.asrPercent += 2.0
                        continue
                    elif string[0].isdigit():
                        num = u""
                        while string and string[0].isdigit():
                            num += string[0]
                            string = string[1:]
                        self.asrPercent = float(num)
                        continue
                    elif string[0] == u"\x0a":
                        self.asrProgressActive = False
                        string = string[1:]
                    else:
                        NSLog(u"unrecognized progress data: %@", string)
                        string = u""
                self.postNotification_({u"action": u"update_progressbar", u"percent": self.asrPercent})
            notification.object().readInBackgroundAndNotify()
    
    def notifyIEDProgressData_(self, notification):
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
            self.postNotification_({u"action": u"update_package_progress", u"percent": progress})
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
            self.postNotification_({u"action": u"update_progress", u"percent": progress})
        elif string.startswith(u"MSG:"):
            message = string[4:]
            self.postNotification_({u"action": u"update_message", u"message": message})
        elif string.startswith(u"PACKAGE:"):
            numstr, _, name = string[8:].partition(u":")
            num = int(numstr)
            self.postNotification_({u"action": u"select_package", u"name": name, u"num": num})
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
        if self.sockPath:
            try:
                self.sock.sendto(msg, self.sockPath)
            except socket.error, e:
                NSLog(u"Socket at %@ failed: %@", self.sockPath, unicode(e))
        else:
            NSLog(u"postNotification:%@", msgDict)
    

def run(args, sockPath, mode):
    NSLog(u'Launching task "%@"', u'" "'.join(args))
    pw = ProgressWatcher.alloc().init()
    pw.watchTask_socket_mode_(args, sockPath, mode)
    runLoop = NSRunLoop.currentRunLoop()
    while pw.shouldKeepRunning():
        runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.distantFuture())
    NSLog(u"Task terminated, exiting")


def installesdtodmg(args):
    if args.cd:
        os.chdir(args.cd)
    pwargs = [u"./installesdtodmg.sh", args.user, args.group, args.output] + args.packages
    run(pwargs, args.socket, u"ied")


def imagescan(args):
    if args.cd:
        os.chdir(args.cd)
    pwargs = [u"/usr/sbin/asr", u"imagescan", u"--source", args.image]
    run(pwargs, args.socket, u"asr")


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument(u"-d", u"--cd", help=u"Set current directory")
    p.add_argument(u"-s", u"--socket", help=u"Communications socket")
    sp = p.add_subparsers(title=u"subcommands", dest=u"subcommand")
    
    iedparser = sp.add_parser(u"installesdtodmg", help=u"Perform installation to DMG")
    iedparser.add_argument(u"-u", u"--user", help=u"Change owner of DMG", required=True)
    iedparser.add_argument(u"-g", u"--group", help=u"Change group of DMG", required=True)
    iedparser.add_argument(u"-o", u"--output", help=u"Set output path", required=True)
    iedparser.add_argument(u"packages", help=u"Additional packages", nargs=u"+")
    iedparser.set_defaults(func=installesdtodmg)
    
    asrparser = sp.add_parser(u"imagescan", help=u"Perform asr imagescan of dmg")
    asrparser.add_argument(u"image", help=u"DMG to scan")
    asrparser.set_defaults(func=imagescan)
    
    args = p.parse_args()
    args.func(args)
    
    return 0
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))
    

#!/usr/bin/python

#-*- coding: utf-8 -*-
#
#  progresswatcher.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-26.
#  Copyright 2013-2014 Per Olofsson, University of Gothenburg. All rights reserved.
#


import os
import sys
import argparse
import socket
import re
import traceback
from Foundation import *


class ProgressWatcher(NSObject):
    
    re_installerlog = re.compile(r'^.+? installer\[[0-9a-f:]+\] (<(?P<level>[^>]+)>:)?(?P<message>.*)$')
    re_number = re.compile(r'^(\d+)')
    re_watchlog = re.compile(r'^.+? (?P<sender>install(d|_monitor))(\[\d+\]): (?P<message>.*)$')
    
    def watchTask_socket_mode_(self, args, sockPath, mode):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sockPath = sockPath
        
        nc = NSNotificationCenter.defaultCenter()
        
        self.isTaskRunning = True
        task = NSTask.alloc().init()
        
        outpipe = NSPipe.alloc().init()
        stdoutHandle = outpipe.fileHandleForReading()
        task.setStandardOutput_(outpipe)
        task.setStandardError_(outpipe)
        
        task.setLaunchPath_(args[0])
        task.setArguments_(args[1:])
        
        if mode == u"asr":
            progressHandler = u"notifyAsrProgressData:"
            self.asrProgressActive = False
            self.asrPhase = 0
        elif mode == u"ied":
            progressHandler = u"notifyIEDProgressData:"
            self.outputBuffer = u""
            self.watchLogHandle = None
            self.watchLogBuffer = u""
            self.lastSender = None
        
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
            progressStr = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if (not self.asrProgressActive) and (u"\x0a" in progressStr):
                progressStr = u"".join(progressStr.partition(u"\x0a")[1:])
            while progressStr:
                if progressStr.startswith(u"\x0a"):
                    progressStr = progressStr[1:]
                    self.asrProgressActive = False
                elif progressStr.startswith(u"Block checksum: "):
                    progressStr = progressStr[16:]
                    self.asrPercent = 0
                    self.asrProgressActive = True
                    self.asrPhase += 1
                    self.postNotification_({u"action": u"select_phase", u"phase": u"asr%d" % self.asrPhase})
                elif progressStr.startswith(u".") and self.asrProgressActive:
                    progressStr = progressStr[1:]
                    self.asrPercent += 2
                    self.postNotification_({u"action": u"update_progress", u"percent": float(self.asrPercent)})
                else:
                    m = self.re_number.match(progressStr)
                    if m and self.asrProgressActive:
                        progressStr = progressStr[len(m.group(0)):]
                        self.asrPercent = int(m.group(0))
                        self.postNotification_({u"action": u"update_progress", u"percent": float(self.asrPercent)})
                    else:
                        self.postNotification_({u"action": u"log_message", u"log_level": 6, u"message": u"asr output: " + progressStr.rstrip()})
                        break
            
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
            elif string.startswith(u"MESSAGE:") or string.startswith(u"PERCENT:"):
                self.parseHdiutilProgress_(string)
            else:
                m = self.re_installerlog.match(string)
                if m:
                    level = m.group(u"level") if m.group(u"level") else u"stderr"
                    message = u"installer.%s: %s" % (level, m.group(u"message"))
                    self.postNotification_({u"action": u"log_message",
                                            u"log_level": 6,
                                            u"message": message})
                else:
                    self.postNotification_({u"action": u"log_message", u"log_level": 6, u"message": string})
        except BaseException as e:
            NSLog(u"Progress parsing failed: %s" % traceback.format_exc())
    
    def parseInstallerProgress_(self, string):
        if string.startswith(u"%"):
            progress = float(string[1:])
            self.postNotification_({u"action": u"update_progress", u"percent": progress})
        elif string.startswith(u"PHASE:"):
            message = string[6:]
            self.postNotification_({u"action": u"update_message", u"message": message})
        elif string.startswith(u"STATUS:"):
            self.postNotification_({u"action": u"log_message", u"log_level": 6, u"message": u"installer: " + string[7:]})
        else:
            self.postNotification_({u"action": u"log_message", u"log_level": 6, u"message": u"installer: " + string})
    
    def parseIEDProgress_(self, string):
        if string.startswith(u"MSG:"):
            message = string[4:]
            self.postNotification_({u"action": u"update_message", u"message": message})
        elif string.startswith(u"PHASE:"):
            phase = string[6:]
            self.postNotification_({u"action": u"select_phase", u"phase": phase})
        elif string.startswith(u"FAILURE:"):
            message = string[8:]
            self.postNotification_({u"action": u"notify_failure", u"message": message})
        elif string.startswith(u"WATCHLOG:"):
            self.watchLog_(string[9:])
        else:
            NSLog(u"(Unknown IED progress %@)", string)
    
    def parseHdiutilProgress_(self, string):
        if string.startswith(u"MESSAGE:"):
            message = string[8:]
            self.postNotification_({u"action": u"update_message", u"message": message})
        elif string.startswith(u"PERCENT:"):
            progress = float(string[8:])
            self.postNotification_({u"action": u"update_progress", u"percent": progress})
    
    def watchLog_(self, cmd):
        if cmd == u"START":
            self.watchLogHandle = NSFileHandle.fileHandleForReadingAtPath_(u"/var/log/install.log")
            self.watchLogHandle.seekToEndOfFile()
            nc = NSNotificationCenter.defaultCenter()
            nc.addObserver_selector_name_object_(self,
                                                 self.notifyWatchLogData_,
                                                 NSFileHandleReadCompletionNotification,
                                                 self.watchLogHandle)
            self.watchLogHandle.readInBackgroundAndNotify()
        elif cmd == u"STOP":
            if self.watchLogHandle:
                self.watchLogHandle.close()
            self.watchLogHandle = None
        else:
            NSLog(u"(Unknown watchLog command: %@)", repr(string))
    
    def notifyWatchLogData_(self, notification):
        data = notification.userInfo()[NSFileHandleNotificationDataItem]
        if data.length():
            string = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if string:
                self.appendWatchLog_(string)
            else:
                NSLog(u"Couldn't decode %@ as UTF-8", data)
            if self.watchLogHandle:
                self.watchLogHandle.readInBackgroundAndNotify()
        else:
            # No data means EOF, so we wait for a second before we try to read
            # again.
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(1.0,
                                                                                     self,
                                                                                     self.readAndNotify_,
                                                                                     self.watchLogHandle,
                                                                                     False)
    
    def readAndNotify_(self, timer):
        if self.watchLogHandle:
            self.watchLogHandle.readInBackgroundAndNotify()
    
    def appendWatchLog_(self, string):
        self.watchLogBuffer += string
        while "\n" in self.watchLogBuffer:
            line, newline, self.watchLogBuffer = self.watchLogBuffer.partition("\n")
            self.parseWatchLog_(line)
    
    def parseWatchLog_(self, string):
        # Multi-line messages start with a tab.
        if string.startswith(u"\t") and self.lastSender:
            message = u"%s: %s" % (self.lastSender, string[1:])
            self.postNotification_({u"action": u"log_message",
                                    u"log_level": 6,
                                    u"message": message})
        else:
            m = self.re_watchlog.match(string)
            if m:
                # Keep track of last sender for multi-line messages.
                self.lastSender = m.group(u"sender")
                message = u"%s: %s" % (m.group(u"sender"), m.group(u"message"))
                self.postNotification_({u"action": u"log_message",
                                        u"log_level": 6,
                                        u"message": message})
            else:
                self.lastSender = None
    
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
    pw = ProgressWatcher.alloc().init()
    pw.watchTask_socket_mode_(args, sockPath, mode)
    runLoop = NSRunLoop.currentRunLoop()
    while pw.shouldKeepRunning():
        runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.distantFuture())


def installesdtodmg(args):
    if args.cd:
        os.chdir(args.cd)
    pwargs = [u"./installesdtodmg.sh", args.user, args.group, args.output, args.volume_name, args.size] + args.packages
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
    iedparser.add_argument(u"-n", u"--volume-name", default=u"Macintosh HD", help=u"Set installed system's volume name.")
    iedparser.add_argument(u"-s", u"--size", default=u"32", help=u"Disk image size in GB.")
    iedparser.add_argument(u"packages", help=u"Packages to install", nargs=u"+")
    iedparser.set_defaults(func=installesdtodmg)
    
    asrparser = sp.add_parser(u"imagescan", help=u"Perform asr imagescan of dmg")
    asrparser.add_argument(u"image", help=u"DMG to scan")
    asrparser.set_defaults(func=imagescan)
    
    args = p.parse_args([x.decode(u"utf-8") for x in argv[1:]])
    args.func(args)
    
    return 0
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))
    

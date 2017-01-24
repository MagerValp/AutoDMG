#!/usr/bin/python

# -*- coding: utf-8 -*-
#
#  progresswatcher.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-26.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

import os
import sys
import argparse
import socket
import re
import traceback
from Foundation import *


MAX_MSG_SIZE = 32768 # See also IEDSL_MAX_MSG_SIZE in IEDSocketListener.


class ProgressWatcher(NSObject):
    
    re_installerlog = re.compile(r'^.+? installer\[[0-9a-f:]+\] (<(?P<level>[^>]+)>:)?(?P<message>.*)$')
    re_number = re.compile(r'^(\d+)')
    re_watchlog = re.compile(r'^.+? (?P<sender>install(d|_monitor))(\[\d+\]): (?P<message>.*)$')
    
    def watchTask_socket_mode_(self, args, sockPath, mode):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, MAX_MSG_SIZE)
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
        
        if mode == "asr":
            progressHandler = "notifyAsrProgressData:"
            self.asrProgressActive = False
            self.asrPhase = 0
        elif mode == "ied":
            progressHandler = "notifyIEDProgressData:"
            self.outputBuffer = ""
            self.watchLogHandle = None
            self.watchLogBuffer = ""
            self.lastSender = None
        
        nc.addObserver_selector_name_object_(self,
                                             progressHandler,
                                             NSFileHandleReadCompletionNotification,
                                             stdoutHandle)
        stdoutHandle.readInBackgroundAndNotify()
        
        nc.addObserver_selector_name_object_(self,
                                             "notifyProgressTermination:",
                                             NSTaskDidTerminateNotification,
                                             task)
        task.launch()
    
    def shouldKeepRunning(self):
        return self.isTaskRunning
    
    def notifyProgressTermination_(self, notification):
        task = notification.object()
        if task.terminationStatus() == 0:
            pass
        self.postNotification_({"action": "task_done", "termination_status": task.terminationStatus()})
        self.isTaskRunning = False
    
    def notifyAsrProgressData_(self, notification):
        data = notification.userInfo()[NSFileHandleNotificationDataItem]
        if data.length():
            progressStr = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if (not self.asrProgressActive) and ("\x0a" in progressStr):
                msg, _, rest = progressStr.partition("\x0a")
                progressStr = "\x0a" + rest
                self.postNotification_({"action": "log_message", "log_level": 6, "message": "asr output: " + msg.rstrip()})
            while progressStr:
                if progressStr.startswith("\x0a"):
                    progressStr = progressStr[1:]
                    self.asrProgressActive = False
                elif progressStr.startswith("Block checksum: "):
                    progressStr = progressStr[16:]
                    self.asrPercent = 0
                    self.asrProgressActive = True
                    self.asrPhase += 1
                    self.postNotification_({"action": "select_phase", "phase": "asr%d" % self.asrPhase})
                elif progressStr.startswith(".") and self.asrProgressActive:
                    progressStr = progressStr[1:]
                    self.asrPercent += 2
                    self.postNotification_({"action": "update_progress", "percent": float(self.asrPercent)})
                else:
                    m = self.re_number.match(progressStr)
                    if m and self.asrProgressActive:
                        progressStr = progressStr[len(m.group(0)):]
                        self.asrPercent = int(m.group(0))
                        self.postNotification_({"action": "update_progress", "percent": float(self.asrPercent)})
                    else:
                        self.postNotification_({"action": "log_message", "log_level": 6, "message": "asr output: " + progressStr.rstrip()})
                        break
            
            notification.object().readInBackgroundAndNotify()
    
    def notifyIEDProgressData_(self, notification):
        data = notification.userInfo()[NSFileHandleNotificationDataItem]
        if data.length():
            string = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if string:
                self.appendOutput_(string)
            else:
                NSLog("Couldn't decode %@ as UTF-8", data)
            notification.object().readInBackgroundAndNotify()
    
    def appendOutput_(self, string):
        self.outputBuffer += string
        while "\n" in self.outputBuffer:
            line, newline, self.outputBuffer = self.outputBuffer.partition("\n")
            self.parseProgress_(line)
    
    def parseProgress_(self, string):
        # Wrap progress parsing so app doesn't crash from bad input.
        try:
            if string.startswith("installer:"):
                self.parseInstallerProgress_(string[10:])
            elif string.startswith("IED:"):
                self.parseIEDProgress_(string[4:])
            elif string.startswith("MESSAGE:") or string.startswith("PERCENT:"):
                self.parseHdiutilProgress_(string)
            else:
                m = self.re_installerlog.match(string)
                if m:
                    level = m.group("level") if m.group("level") else "stderr"
                    message = "installer.%s: %s" % (level, m.group("message"))
                    self.postNotification_({"action": "log_message",
                                            "log_level": 6,
                                            "message": message})
                else:
                    self.postNotification_({"action": "log_message", "log_level": 6, "message": string})
        except BaseException as e:
            NSLog("Progress parsing failed: %@", traceback.format_exc())
    
    def parseInstallerProgress_(self, string):
        if string.startswith("%"):
            progress = float(string[1:])
            self.postNotification_({"action": "update_progress", "percent": progress})
        elif string.startswith("PHASE:"):
            message = string[6:]
            self.postNotification_({"action": "update_message", "message": message})
        elif string.startswith("STATUS:"):
            self.postNotification_({"action": "log_message", "log_level": 6, "message": "installer: " + string[7:]})
        else:
            self.postNotification_({"action": "log_message", "log_level": 6, "message": "installer: " + string})
    
    def parseIEDProgress_(self, string):
        if string.startswith("MSG:"):
            message = string[4:]
            self.postNotification_({"action": "update_message", "message": message})
        elif string.startswith("PHASE:"):
            phase = string[6:]
            self.postNotification_({"action": "select_phase", "phase": phase})
        elif string.startswith("FAILURE:"):
            message = string[8:]
            self.postNotification_({"action": "notify_failure", "message": message})
        elif string.startswith("SUCCESS:"):
            message = string[8:]
            self.postNotification_({"action": "notify_success", "message": message})
        elif string.startswith("WATCHLOG:"):
            self.watchLog_(string[9:])
        else:
            NSLog("(Unknown IED progress %@)", string)
    
    def parseHdiutilProgress_(self, string):
        if string.startswith("MESSAGE:"):
            message = string[8:]
            self.postNotification_({"action": "update_message", "message": message})
        elif string.startswith("PERCENT:"):
            progress = float(string[8:])
            self.postNotification_({"action": "update_progress", "percent": progress})
    
    def watchLog_(self, cmd):
        if cmd == "START":
            self.watchLogHandle = NSFileHandle.fileHandleForReadingAtPath_("/var/log/install.log")
            self.watchLogHandle.seekToEndOfFile()
            nc = NSNotificationCenter.defaultCenter()
            nc.addObserver_selector_name_object_(self,
                                                 self.notifyWatchLogData_,
                                                 NSFileHandleReadCompletionNotification,
                                                 self.watchLogHandle)
            self.watchLogHandle.readInBackgroundAndNotify()
        elif cmd == "STOP":
            if self.watchLogHandle:
                try:
                    self.watchLogHandle.close()
                except AttributeError:
                    pass
            self.watchLogHandle = None
        else:
            NSLog("(Unknown watchLog command: %@)", repr(string))
    
    def notifyWatchLogData_(self, notification):
        data = notification.userInfo()[NSFileHandleNotificationDataItem]
        if data.length():
            string = NSString.alloc().initWithData_encoding_(data, NSUTF8StringEncoding)
            if string:
                self.appendWatchLog_(string)
            else:
                NSLog("Couldn't decode %@ as UTF-8", data)
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
        if string.startswith("\t") and self.lastSender:
            message = "%s: %s" % (self.lastSender, string[1:])
            self.postNotification_({"action": "log_message",
                                    "log_level": 6,
                                    "message": message})
        else:
            m = self.re_watchlog.match(string)
            if m:
                # Keep track of last sender for multi-line messages.
                self.lastSender = m.group("sender")
                message = "%s: %s" % (m.group("sender"), m.group("message"))
                self.postNotification_({"action": "log_message",
                                        "log_level": 6,
                                        "message": message})
            else:
                self.lastSender = None
    
    def postNotification_(self, msgDict):
        msg, error = NSPropertyListSerialization.dataWithPropertyList_format_options_error_(msgDict,
                                                                                            NSPropertyListBinaryFormat_v1_0,
                                                                                            0,
                                                                                            None)
        if not msg:
            if error:
                NSLog("plist encoding failed: %@", error)
            return
        if self.sockPath:
            try:
                self.sock.sendto(msg, self.sockPath)
            except socket.error as e:
                NSLog("Socket at %@ failed: %@", self.sockPath, str(e))
                NSLog("Failed socket message: %@", msg)
        else:
            NSLog("postNotification:%@", msgDict)
    

def run(args, sockPath, mode):
    pw = ProgressWatcher.alloc().init()
    pw.watchTask_socket_mode_(args, sockPath, mode)
    runLoop = NSRunLoop.currentRunLoop()
    while pw.shouldKeepRunning():
        runLoop.runMode_beforeDate_(NSDefaultRunLoopMode, NSDate.distantFuture())


def installesdtodmg(args):
    if (os.geteuid() == 0) and (os.getuid() != 0):
        os.setuid(0)
    NSLog("progresswatcher uid: %d, euid: %d", os.getuid(), os.geteuid())
    if args.cd:
        os.chdir(args.cd)
    if args.baseimage:
        baseimage = [args.baseimage]
    else:
        baseimage = []
    pwargs = ["./installesdtodmg.sh",
              args.user,
              args.group,
              args.output,
              args.volume_name,
              args.size,
              args.template] + baseimage + args.packages
    run(pwargs, args.socket, "ied")


def imagescan(args):
    if args.cd:
        os.chdir(args.cd)
    pwargs = ["/usr/sbin/asr", "imagescan", "--source", args.image]
    run(pwargs, args.socket, "asr")


def main(argv):
    NSLog("progresswatcher launching")
    NSLog("progresswatcher arguments: %@", argv)
    NSLog("progresswatcher uid: %d, euid: %d", os.getuid(), os.geteuid())
    NSLog("progresswatcher language: %@", NSLocale.currentLocale().objectForKey_(NSLocaleLanguageCode))
    
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--cd", help="Set current directory")
    p.add_argument("-s", "--socket", help="Communications socket")
    sp = p.add_subparsers(title="subcommands", dest="subcommand")
    
    iedparser = sp.add_parser("installesdtodmg", help="Perform installation to DMG")
    iedparser.add_argument("-u", "--user", help="Change owner of DMG", required=True)
    iedparser.add_argument("-g", "--group", help="Change group of DMG", required=True)
    iedparser.add_argument("-o", "--output", help="Set output path", required=True)
    iedparser.add_argument("-t", "--template", help="Path to adtmpl", required=True)
    iedparser.add_argument("-n", "--volume-name", default="Macintosh HD", help="Set installed system's volume name.")
    iedparser.add_argument("-s", "--size", default="32", help="Disk image size in GB.")
    iedparser.add_argument("-b", "--baseimage", default=None, help="Base system image for shadow mount.")
    iedparser.add_argument("packages", help="Packages to install", nargs="+")
    iedparser.set_defaults(func=installesdtodmg)
    
    asrparser = sp.add_parser("imagescan", help="Perform asr imagescan of dmg")
    asrparser.add_argument("image", help="DMG to scan")
    asrparser.set_defaults(func=imagescan)
    
    try:
        args = p.parse_args([x.decode("utf-8") for x in argv[1:]])
        args.func(args)
    except:
        NSLog("progresswatcher died with an uncaught exception: %@", traceback.format_exc())
        return os.EX_SOFTWARE
    
    return 0
    

if __name__ == '__main__':
    sys.exit(main(sys.argv))

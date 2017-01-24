# -*- coding: utf-8 -*-
#
#  IEDLog.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-25.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals
from __future__ import print_function

from Foundation import *
from AppKit import *
from objc import IBAction, IBOutlet

from IEDLogLine import *
from IEDPanelPathManager import *
import inspect
import syslog
import sys
import traceback


IEDLogLevelEmergency = 0
IEDLogLevelAlert     = 1
IEDLogLevelCritical  = 2
IEDLogLevelError     = 3
IEDLogLevelWarning   = 4
IEDLogLevelNotice    = 5
IEDLogLevelInfo      = 6
IEDLogLevelDebug     = 7
IEDColorForLevel = [
    NSColor.redColor(),
    NSColor.redColor(),
    NSColor.redColor(),
    NSColor.redColor(),
    NSColor.orangeColor(),
    NSColor.blackColor(),
    NSColor.blackColor(),
    NSColor.grayColor(),
]

# Control which output channels are active.
IEDLogToController  = True
IEDLogToSyslog      = True
IEDLogToStdOut      = False
IEDLogToFile        = False

# Default log levels.
IEDLogStdOutLogLevel    = IEDLogLevelNotice
IEDLogFileLogLevel      = IEDLogLevelDebug

# File handle for log file.
IEDLogFileHandle = None


defaults = NSUserDefaults.standardUserDefaults()


def IEDLogLevelName(level):
    return (
        "Emergency",
        "Alert",
        "Critical",
        "Error",
        "Warning",
        "Notice",
        "Info",
        "Debug",
    )[level]


def LogException(func):
    """Wrap IBActions to catch exceptions."""
    def wrapper(c, s):
        global _log
        try:
            func(c, s)
        except Exception as e:
            exceptionInfo = traceback.format_exc()
            LogDebug("Uncaught exception in %@, %@", func.__name__, exceptionInfo.rstrip())
            alert = NSAlert.alloc().init()
            alert.setMessageText_("Uncaught exception")
            alert.setInformativeText_(exceptionInfo)
            alert.addButtonWithTitle_("Dismiss")
            alert.addButtonWithTitle_("Save Log…")
            while alert.runModal() == NSAlertSecondButtonReturn:
                _log.saveLog_(IEDLog.IEDLog, None)
    return wrapper


class IEDLog(NSObject):
    
    # Singleton instance.
    _instance = None
    
    logWindow = IBOutlet()
    logTableView = IBOutlet()
    levelSelector = IBOutlet()
    
    logLines = list()
    visibleLogLines = list()
    
    def init(self):
        # Initialize singleton.
        if IEDLog._instance is not None:
            return IEDLog._instance
        self = super(IEDLog, self).init()
        if self is None:
            return None
        IEDLog._instance = self
        self.logAtBottom = True
        return self
    
    def awakeFromNib(self):
        global defaults
        self.levelSelector.selectItemAtIndex_(defaults.integerForKey_("LogLevel"))
        self.logTableView.setDataSource_(self)
        self.logTableView.setDelegate_(self)
        self.messageColumnWidth = self.logTableView.tableColumnWithIdentifier_("message").width()
        nc = NSNotificationCenter.defaultCenter()
        nc.addObserver_selector_name_object_(self,
                                             self.logViewScrolled_,
                                             NSViewBoundsDidChangeNotification,
                                             self.logTableView.enclosingScrollView().contentView())
    
    # Helper methods.
    
    
    def addMessage_level_(self, message, level):
        # Log messages may come from background threads.
        self.performSelectorOnMainThread_withObject_waitUntilDone_(self.addMessageAndLevel_,
                                                                   {"message": message,
                                                                    "level": level},
                                                                   False)
    
    def addMessageAndLevel_(self, messageAndLevel):
        message = messageAndLevel["message"]
        level = messageAndLevel["level"]
        logLine = IEDLogLine.alloc().initWithMessage_level_(message, level)
        self.logLines.append(logLine)
        if defaults.integerForKey_("LogLevel") >= level:
            self.visibleLogLines.append(logLine)
            if self.logTableView:
                self.logTableView.reloadData()
                if self.logAtBottom:
                    self.logTableView.scrollRowToVisible_(len(self.visibleLogLines) - 1)
    
    
    
    # Act on user showing log window.
    
    @LogException
    @IBAction
    def displayLogWindow_(self, sender):
        self.logAtBottom = True
        self.logTableView.scrollRowToVisible_(len(self.visibleLogLines) - 1)
        self.logWindow.makeKeyAndOrderFront_(self)
    
    
    
    # Act on notification for log being scrolled by user.
    
    def logViewScrolled_(self, notification):
        tableViewHeight = self.logTableView.bounds().size.height
        scrollView = self.logTableView.enclosingScrollView()
        scrollRect = scrollView.documentVisibleRect()
        scrollPos = scrollRect.origin.y + scrollRect.size.height
        
        if scrollPos >= tableViewHeight:
            self.logAtBottom = True
        else:
            self.logAtBottom = False
    
    # Act on user filtering log.
    
    @LogException
    @IBAction
    def setLevel_(self, sender):
        self.visibleLogLines = [x for x in self.logLines if x.level() <= self.levelSelector.indexOfSelectedItem()]
        self.logAtBottom = True
        self.logTableView.reloadData()
        self.logTableView.scrollRowToVisible_(len(self.visibleLogLines) - 1)
    
    
    
    # Act on user clicking save button.
    
    @LogException
    @IBAction
    def saveLog_(self, sender):
        IEDPanelPathManager.loadPathForName_("Log")
        
        panel = NSSavePanel.savePanel()
        panel.setExtensionHidden_(False)
        panel.setAllowedFileTypes_(["log", "txt"])
        formatter = NSDateFormatter.alloc().init()
        formatter.setDateFormat_("yyyy-MM-dd HH.mm")
        dateStr = formatter.stringFromDate_(NSDate.date())
        panel.setNameFieldStringValue_("AutoDMG %s" % dateStr)
        result = panel.runModal()
        if result != NSFileHandlingPanelOKButton:
            return
        
        IEDPanelPathManager.savePathForName_("Log")
        
        exists, error = panel.URL().checkResourceIsReachableAndReturnError_(None)
        if exists:
            success, error = NSFileManager.defaultManager().removeItemAtURL_error_(panel.URL(), None)
            if not success:
                NSApp.presentError_(error)
                return
        
        success, error = NSData.data().writeToURL_options_error_(panel.URL(), 0, None)
        if not success:
            NSApp.presentError_(error)
            return
        
        fh, error = NSFileHandle.fileHandleForWritingToURL_error_(panel.URL(), None)
        if fh is None:
            NSAlert.alertWithError_(error).runModal()
            return
        formatter = NSDateFormatter.alloc().init()
        formatter.setDateFormat_("yyyy-MM-dd HH:mm:ss")
        for logLine in self.logLines:
            textLine = NSString.stringWithFormat_("%@ %@: %@\n",
                                                  formatter.stringFromDate_(logLine.date()),
                                                  IEDLogLevelName(logLine.level()),
                                                  logLine.message())
            fh.writeData_(textLine.dataUsingEncoding_(NSUTF8StringEncoding))
        fh.closeFile()
    
    
    
    # We're an NSTableViewDataSource.
    
    def numberOfRowsInTableView_(self, tableView):
        return len(self.visibleLogLines)
    
    def attrString_forRow_(self, s, row):
        color = IEDColorForLevel[self.visibleLogLines[row].level()]
        attr = {NSForegroundColorAttributeName: color}
        return NSAttributedString.alloc().initWithString_attributes_(s, attr)
    
    def tableView_objectValueForTableColumn_row_(self, tableView, column, row):
        if column.identifier() == "date":
            return self.visibleLogLines[row].date()
        elif column.identifier() == "level":
            return self.attrString_forRow_(IEDLogLevelName(self.visibleLogLines[row].level()), row)
        elif column.identifier() == "message":
            return self.attrString_forRow_(self.visibleLogLines[row].message(), row)
        else:
            LogDebug("Unexpected column identifier '%@'", column.identifier())
    
    
    
    # We're an NSTableViewDelegate.
    
    def tableViewColumnDidResize_(self, notification):
        self.messageColumnWidth = self.logTableView.tableColumnWithIdentifier_("message").width()
        changeRange = NSMakeRange(0, self.logTableView.numberOfRows())
        changeSet = NSIndexSet.indexSetWithIndexesInRange_(changeRange)
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.0)
        self.logTableView.noteHeightOfRowsWithIndexesChanged_(changeSet)
        NSAnimationContext.endGrouping()
    
    def tableView_heightOfRow_(self, tableView, row):
        text = NSString.stringWithString_(self.visibleLogLines[row].message())
        font = NSFont.userFixedPitchFontOfSize_(11.0)
        rect = text.boundingRectWithSize_options_attributes_context_(NSMakeSize(self.messageColumnWidth - 4, 1000),
                                                                     NSStringDrawingUsesLineFragmentOrigin,
                                                                     {NSFontAttributeName: font},
                                                                     None)
        return rect.size.height



timestampFormatter = NSDateFormatter.alloc().init()
timestampFormatter.setDateStyle_(NSDateFormatterLongStyle)
timestampFormatter.setTimeStyle_(NSDateFormatterLongStyle)

def timestamp(dt=None):
    global timestampFormatter
    if dt is None:
        dt = NSDate.date()
    return timestampFormatter.stringFromDate_(dt)


def LogToSyslog(level, message):
    syslog.syslog(level, message.encode("utf-8"))


def LogToStdOut(level, message):
    print(message.encode("utf-8"), file=sys.stdout)


def LogToFile(level, message):
    global IEDLogFileHandle
    if IEDLogFileHandle is not None:
        print(NSString.stringWithFormat_("%@  %@",
                                         timestamp(),
                                         message).encode("utf-8"),
                                         file=IEDLogFileHandle)
    else:
        NSLog("IEDLogFileHandle not open")


# Keep (singleton) instance of IEDLog.
_log = IEDLog.alloc().init()

def LogMessage(level, message):
    global _log
    
    # Prefix debug messages with the module name and line number.
    prefix = ""
    if level == IEDLogLevelDebug:
        for caller in inspect.stack()[1:]:
            modname = inspect.getmodule(caller[0]).__name__
            if modname == "IEDLog":
                continue
            lineno = caller[2]
            prefix = "(%s:%d) " % (modname, lineno)
            break
    
    # Control syslog verbosity with DebugToSyslog bool.
    if defaults.boolForKey_("DebugToSyslog"):
        syslogLevel = IEDLogLevelDebug
    else:
        syslogLevel = IEDLogLevelInfo
    
    # Log each line as a separate message.
    for line in message.split("\n"):
        
        # Prepend prefix.
        prefixedLine = prefix + line
        
        # Dispatch line to each active channel.
        
        if IEDLogToController:
            _log.addMessage_level_(prefixedLine, level)
        
        if IEDLogToSyslog and (level <= syslogLevel):
            LogToSyslog(level, prefixedLine)
        
        if IEDLogToStdOut and (level <= IEDLogStdOutLogLevel):
            LogToStdOut(level, prefixedLine)
        
        if IEDLogToFile and (level <= IEDLogFileLogLevel):
            LogToFile(level, prefixedLine)

def LogDebug(*args):
    LogMessage(IEDLogLevelDebug, NSString.stringWithFormat_(*args))

def LogInfo(*args):
    LogMessage(IEDLogLevelInfo, NSString.stringWithFormat_(*args))

def LogNotice(*args):
    LogMessage(IEDLogLevelNotice, NSString.stringWithFormat_(*args))

def LogWarning(*args):
    LogMessage(IEDLogLevelWarning, NSString.stringWithFormat_(*args))

def LogError(*args):
    LogMessage(IEDLogLevelError, NSString.stringWithFormat_(*args))

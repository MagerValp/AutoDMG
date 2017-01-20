# -*- coding: utf-8 -*-
#
#  main.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals
from __future__ import print_function

import os
import sys
import argparse
import traceback

import objc
import Foundation

objc.setVerbose(True)

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
import IEDLog
from IEDUtil import *
import platform


def get_date_string():
    formatter = NSDateFormatter.alloc().init()
    formatter.setDateFormat_("yyyy-MM-dd")
    return formatter.stringFromDate_(NSDate.date())

def get_log_dir():
    logDir = os.path.expanduser("~/Library/Logs/AutoDMG")
    if not os.path.exists(logDir):
        try:
            os.makedirs(logDir)
        except OSError as e:
            LogWarning("Couldn't create %@", logDir)
    return logDir


def gui_unexpected_error_alert():
    try:
        exceptionInfo = traceback.format_exc()
    except:
        exceptionInfo = "(no traceback available)"
    NSLog("AutoDMG died with an uncaught exception: %@", exceptionInfo)
    from AppKit import NSAlertSecondButtonReturn
    alert = NSAlert.alloc().init()
    alert.setMessageText_("AutoDMG died with an uncaught exception")
    alert.setInformativeText_(exceptionInfo)
    alert.addButtonWithTitle_("Quit")
    alert.addButtonWithTitle_("Save Log…")
    while alert.runModal() == NSAlertSecondButtonReturn:
        IEDLog.IEDLog.saveLog_(IEDLog.IEDLog, None)
    sys.exit(os.EX_SOFTWARE)

def gui_main():
    IEDLog.IEDLogToController  = True
    IEDLog.IEDLogToSyslog      = True
    IEDLog.IEDLogToStdOut      = True
    IEDLog.IEDLogStdOutLogLevel = IEDLog.IEDLogLevelDebug
    logFile = os.path.join(get_log_dir(), "AutoDMG-%s.log" % get_date_string())
    try:
        IEDLog.IEDLogFileHandle = open(logFile, "a", buffering=1)
        IEDLog.IEDLogToFile = True
    except IOError as e:
        IEDLog.IEDLogToFile = False
        LogWarning("Couldn't open %@ for writing", logFile)
    
    import AppKit
    from PyObjCTools import AppHelper
    
    # import modules containing classes required to start application and load MainMenu.nib
    import IEDAppDelegate
    import IEDController
    import IEDSourceSelector
    import IEDAddPkgController
    import IEDAppVersionController
    
    # pass control to AppKit
    AppHelper.runEventLoop(unexpectedErrorAlert=gui_unexpected_error_alert)
    
    return os.EX_OK


def cli_main(argv):
    IEDLog.IEDLogToController  = False
    IEDLog.IEDLogToSyslog      = True
    IEDLog.IEDLogToStdOut      = True
    IEDLog.IEDLogToFile        = False
    
    from IEDCLIController import IEDCLIController
    clicontroller = IEDCLIController.alloc().init()
    
    try:
        # Initialize user defaults before application starts.
        defaults = NSUserDefaults.standardUserDefaults()
        defaultsPath = NSBundle.mainBundle().pathForResource_ofType_("Defaults", "plist")
        defaultsDict = NSDictionary.dictionaryWithContentsOfFile_(defaultsPath)
        defaults.registerDefaults_(defaultsDict)
        
        p = argparse.ArgumentParser()
        p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
        p.add_argument("-L", "--log-level",
                       type=int, choices=range(0, 8), default=6,
                       metavar="LEVEL", help="Log level (0-7), default 6")
        p.add_argument("-l", "--logfile", help="Log to file")
        p.add_argument("-r", "--root", action="store_true", help="Allow running as root")
        sp = p.add_subparsers(title="subcommands", dest="subcommand")
        
        # Populate subparser for each verb.
        for verb in clicontroller.listVerbs():
            verb_method = getattr(clicontroller, "cmd%s_" % verb.capitalize())
            addargs_method = getattr(clicontroller, "addargs%s_" % verb.capitalize())
            parser = sp.add_parser(verb, help=verb_method.__doc__)
            addargs_method(parser)
            parser.set_defaults(func=verb_method)
        
        args = p.parse_args(argv)
        
        if args.verbose:
            IEDLog.IEDLogStdOutLogLevel = IEDLog.IEDLogLevelInfo
        else:
            IEDLog.IEDLogStdOutLogLevel = IEDLog.IEDLogLevelNotice
        
        IEDLog.IEDLogFileLogLevel = args.log_level
        
        if args.logfile == "-":
            # Redirect log to stdout instead.
            IEDLog.IEDLogFileHandle = sys.stdout
            IEDLog.IEDLogToFile = True
            IEDLog.IEDLogToStdOut = False
        else:
            try:
                if args.logfile:
                    logFile = args.logfile
                else:
                    logFile = os.path.join(get_log_dir(), "AutoDMG-%s.log" % get_date_string())
                IEDLog.IEDLogFileHandle = open(logFile, "a", buffering=1)
            except (IOError, OSError) as e:
                print(("Couldn't open %s for writing" % logFile).encode("utf-8"), file=sys.stderr)
                return os.EX_CANTCREAT
            IEDLog.IEDLogToFile = True
        
        # Check if we're running with root.
        if os.getuid() == 0:
            if args.root:
                fm = NSFileManager.defaultManager()
                url, error = fm.URLForDirectory_inDomain_appropriateForURL_create_error_(NSApplicationSupportDirectory,
                                                                                         NSUserDomainMask,
                                                                                         None,
                                                                                         False,
                                                                                         None)
                LogWarning("Running as root, using %@", os.path.join(url.path(), "AutoDMG"))
            else:
                LogError("Running as root isn't recommended (use -r to override)")
                return os.EX_USAGE
        
        # Log version info on startup.
        version, build = IEDUtil.getAppVersion()
        LogInfo("AutoDMG v%@ build %@", version, build)
        name, version, build = IEDUtil.readSystemVersion_("/")
        LogInfo("%@ %@ %@", name, version, build)
        LogInfo("%@ %@ (%@)", platform.python_implementation(),
                               platform.python_version(),
                               platform.python_compiler())
        LogInfo("PyObjC %@", objc.__version__)
        
        return args.func(args)
    finally:
        clicontroller.cleanup()


def main():
    # Global exception handler to make sure we always log tracebacks.
    try:
        
        # Decode arguments as utf-8 and filter out arguments from Finder and
        # Xcode.
        decoded_argv = list()
        i = 1
        while i < len(sys.argv):
            arg = sys.argv[i].decode("utf-8")
            if arg.startswith("-psn"):
                pass
            elif arg == "-NSDocumentRevisionsDebugMode":
                i += 1
            elif arg.startswith("-NS"):
                pass
            else:
                decoded_argv.append(arg)
            i += 1
        
        # Ensure trailing slash on TMPDIR.
        try:
            tmpdir = os.getenv("TMPDIR")
            if tmpdir:
                if os.path.isdir(tmpdir):
                    if not tmpdir.endswith("/"):
                        NSLog("Fixing trailing slash on TMPDIR '%@'", tmpdir)
                        os.environ["TMPDIR"] = tmpdir + "/"
                        NSLog("TMPDIR is now '%@'", os.getenv("TMPDIR"))
                else:
                    NSLog("TMPDIR is not a valid directory: '%@'", tmpdir)
            else:
                NSLog("TMPDIR is not set")
        except Exception as e:
            NSLog("TMPDIR trailing slash fix failed with exception: %@", str(e))
        
        # If no arguments are supplied, assume the GUI should be started.
        if len(decoded_argv) == 0:
            return gui_main()
        # Otherwise parse the command line arguments.
        else:
            status = cli_main(decoded_argv)
            return status
    
    except SystemExit as e:
        NSLog("main() exited with code %d", e.code)
        return e.code
    except Exception as e:
        try:
            exceptionInfo = traceback.format_exc()
        except:
            exceptionInfo = "(no traceback available)"
        NSLog("AutoDMG died with an uncaught exception %@: %@", str(e), exceptionInfo)
        return os.EX_SOFTWARE
    finally:
        # Explicitly close stdout/stderr to avoid Python issue 11380.
        try:
            sys.stdout.close()
        except:
            pass
        try:
            sys.stderr.close()
        except:
            pass


if __name__ == '__main__':
    sys.exit(main())

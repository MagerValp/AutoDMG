# -*- coding: utf-8 -*-
#
#  main.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-09-19.
#  Copyright 2013-2014 Per Olofsson, University of Gothenburg. All rights reserved.
#

import os
import sys
import argparse
import traceback

import objc
import Foundation

from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
import IEDLog
from IEDUtil import *
import platform


def gui_unexpected_error_alert():
    exceptionInfo = traceback.format_exc()
    NSLog(u"AutoDMG died with an uncaught exception, %@", exceptionInfo)
    from AppKit import NSAlertSecondButtonReturn
    alert = NSAlert.alloc().init()
    alert.setMessageText_(u"AutoDMG died with an uncaught exception")
    alert.setInformativeText_(exceptionInfo)
    alert.addButtonWithTitle_(u"Quit")
    alert.addButtonWithTitle_(u"Save Log…")
    while alert.runModal() == NSAlertSecondButtonReturn:
        IEDLog.IEDLog.saveLog_(IEDLog.IEDLog, None)
    sys.exit(os.EX_SOFTWARE)

def gui_main():
    IEDLog.IEDLogToController  = True
    IEDLog.IEDLogToSyslog      = True
    IEDLog.IEDLogToStdOut      = True
    IEDLog.IEDLogToFile        = False
    
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
        defaultsPath = NSBundle.mainBundle().pathForResource_ofType_(u"Defaults", u"plist")
        defaultsDict = NSDictionary.dictionaryWithContentsOfFile_(defaultsPath)
        defaults.registerDefaults_(defaultsDict)
        
        p = argparse.ArgumentParser()
        p.add_argument(u"-v", u"--verbose", action=u"store_true", help=u"Verbose output")
        p.add_argument(u"-L", u"--log-level",
                       type=int, choices=range(0, 8), default=6,
                       metavar=u"LEVEL", help=u"Log level (0-7), default 6")
        p.add_argument(u"-l", u"--logfile", help=u"Log to file")
        p.add_argument(u"-r", u"--root", action=u"store_true", help=u"Allow running as root")
        sp = p.add_subparsers(title=u"subcommands", dest=u"subcommand")
        
        # Populate subparser for each verb.
        for verb in clicontroller.listVerbs():
            verb_method = getattr(clicontroller, u"cmd%s_" % verb.capitalize())
            addargs_method = getattr(clicontroller, u"addargs%s_" % verb.capitalize())
            parser = sp.add_parser(verb, help=verb_method.__doc__)
            addargs_method(parser)
            parser.set_defaults(func=verb_method)
        
        args = p.parse_args(argv)
        
        if args.verbose:
            IEDLog.IEDLogStdOutLogLevel = IEDLog.IEDLogLevelInfo
        else:
            IEDLog.IEDLogStdOutLogLevel = IEDLog.IEDLogLevelNotice
        
        IEDLog.IEDLogFileLogLevel = args.log_level
        
        if args.logfile:
            if args.logfile == u"-":
                # Redirect log to stdout instead.
                IEDLog.IEDLogFileHandle = sys.stdout
                IEDLog.IEDLogToStdOut = False
            else:
                try:
                    IEDLog.IEDLogFileHandle = open(args.logfile, u"a", buffering=1)
                except OSError as e:
                    print >>sys.stderr, (u"Couldn't open %s for writing" % (args.logfile)).encode(u"utf-8")
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
                LogWarning(u"Running as root, using %@", os.path.join(url.path(), u"AutoDMG"))
            else:
                LogError(u"Running as root isn't recommended (use -r to override)")
                return os.EX_USAGE
        
        # Log version info on startup.
        version, build = IEDUtil.getAppVersion()
        LogInfo(u"AutoDMG v%@ build %@", version, build)
        name, version, build = IEDUtil.readSystemVersion_(u"/")
        LogInfo(u"%@ %@ %@", name, version, build)
        LogInfo(u"%@ %@ (%@)", platform.python_implementation(),
                               platform.python_version(),
                               platform.python_compiler())
        LogInfo(u"PyObjC %@", objc.__version__)
        
        return args.func(args)
    finally:
        clicontroller.cleanup()


# Global exception handler to make sure we always log tracebacks.
try:

    # Decode arguments as utf-8 and filter out arguments from Finder and
    # Xcode.
    decoded_argv = list()
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i].decode(u"utf-8")
        if arg.startswith(u"-psn"):
            pass
        elif arg == u"-NSDocumentRevisionsDebugMode":
            i += 1
        elif arg.startswith(u"-NS"):
            pass
        else:
            decoded_argv.append(arg)
        i += 1

    # If no arguments are supplied, assume the GUI should be started.
    if len(decoded_argv) == 0:
        sys.exit(gui_main())
    # Otherwise parse the command line arguments.
    else:
        sys.exit(cli_main(decoded_argv))

except Exception:
    NSLog(u"AutoDMG died with an uncaught exception, %@", traceback.format_exc())
    sys.exit(os.EX_SOFTWARE)

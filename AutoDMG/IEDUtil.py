#-*- coding: utf-8 -*-
#
#  IEDUtil.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright (c) 2013 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *
from Carbon.File import *
import MacOS

import os.path
import subprocess
import tempfile
import shutil
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage
IEDMountInfo = objc.lookUpClass(u"IEDMountInfo")


class IEDUtil(NSObject):
    
    VERSIONPLIST_PATH = u"System/Library/CoreServices/SystemVersion.plist"
    
    @classmethod
    def readSystemVersion_(cls, rootPath):
        plist = NSDictionary.dictionaryWithContentsOfFile_(os.path.join(rootPath, cls.VERSIONPLIST_PATH))
        name = plist[u"ProductName"]
        version = plist[u"ProductUserVisibleVersion"]
        build = plist[u"ProductBuildVersion"]
        return (name, version, build)
    
    @classmethod
    def getAppVersion(cls):
        bundle = NSBundle.mainBundle()
        version = bundle.objectForInfoDictionaryKey_(u"CFBundleShortVersionString")
        build = bundle.objectForInfoDictionaryKey_(u"CFBundleVersion")
        return (version, build)
    
    @classmethod
    def resolvePath_(cls, path):
        """Expand symlinks and resolve aliases."""
        try:
            fsref, isFolder, wasAliased = FSResolveAliasFile(os.path.realpath(path), 1)
            return os.path.abspath(fsref.as_pathname().decode(u"utf-8"))
        except MacOS.Error as e:
            return None
    
    @classmethod
    def installESDPath_(cls, path):
        u"""Resolve aliases and return path to InstallESD."""
        path = cls.resolvePath_(path)
        if not path:
            return None
        if os.path.exists(os.path.join(path,
                          u"Contents/SharedSupport/InstallESD.dmg")):
            return path
        if (os.path.basename(path).lower().startswith(u"installesd") and \
            os.path.basename(path).lower().endswith(u".dmg")) and \
           os.path.exists(path):
            return path
        else:
            return None
    
    @classmethod
    def getPackageSize_(cls, path):
        p = subprocess.Popen([u"/usr/bin/du", u"-sk", path],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            LogError(u"du failed with exit code %d", p.returncode)
            return 0
        else:
            return int(out.split()[0]) * 1024
    
    @classmethod
    def formatBytes_(cls, bytes):
        bytes = float(bytes)
        unitIndex = 0
        while len(str(int(bytes))) > 3:
            bytes /= 1000.0
            unitIndex += 1
        return u"%.1f %s" % (bytes, (u"bytes", u"kB", u"MB", u"GB", u"TB")[unitIndex])
    
    @classmethod
    def findMountPoint_(cls, path):
        path = os.path.abspath(path)
        while not os.path.ismount(path):
            path = os.path.dirname(path)
        return path
    
    @classmethod
    def getInstalledPkgSize_(cls, pkgPath):
        pkgFileName = os.path.os.path.basename(pkgPath)
        tempdir = tempfile.mkdtemp()
        try:
            symlinkPath = os.path.join(tempdir, pkgFileName)
            os.symlink(pkgPath, symlinkPath)
            p = subprocess.Popen([u"/usr/sbin/installer",
                                 u"-pkginfo",
                                 u"-verbose",
                                 u"-plist",
                                 u"-pkg",
                                 symlinkPath],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
        finally:
            try:
                shutil.rmtree(tempdir)
            except BaseException as e:
                LogWarning(u"Unable to remove tempdir: %@", unicode(e))
        if p.returncode != 0:
            mountPoints = IEDMountInfo.getMountPoints()
            fsInfo = mountPoints[cls.findMountPoint_(pkgPath)]
            if not fsInfo[u"islocal"]:
                LogWarning(u"Estimating package size since installer -pkginfo " \
                           u"failed and '%@' is on a remote (%@) filesystem",
                           pkgPath, fsInfo[u"fstypename"])
                return cls.getPackageSize_(pkgPath) * 2
            else:
                LogError(u"installer -pkginfo -pkg '%@' failed with exit code %d", pkgPath, p.returncode)
                return None
        outData = NSData.dataWithBytes_length_(out, len(out))
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(outData,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            LogError(u"Error decoding plist: %@", error)
            return None
        LogDebug(u"%@ requires %@", pkgPath, cls.formatBytes_(int(plist[u"Size"])* 1024))
        return int(plist[u"Size"]) * 1024



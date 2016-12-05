# -*- coding: utf-8 -*-
#
#  IEDUtil.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from Foundation import *

import os.path
import subprocess
import tempfile
import shutil
import platform
from xml.etree import ElementTree
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


class IEDUtil(NSObject):
    
    VERSIONPLIST_PATH = u"System/Library/CoreServices/SystemVersion.plist"
    PACKAGE_EXTENSIONS = [u".pkg", u".mpkg", u".app", u".dmg"]
    
    @classmethod
    def readSystemVersion_(cls, rootPath):
        """Read SystemVersion.plist on the specified volume."""
        plist = NSDictionary.dictionaryWithContentsOfFile_(os.path.join(rootPath, cls.VERSIONPLIST_PATH))
        name = plist[u"ProductName"]
        version = plist[u"ProductUserVisibleVersion"]
        build = plist[u"ProductBuildVersion"]
        return (name, version, build)
    
    @classmethod
    def splitVersion(cls, versionString, strip=u""):
        """Split version string into a tuple of ints."""
        return tuple(int(x.strip(strip)) for x in versionString.split(u"."))
    
    @classmethod
    def hostVersionTuple(cls):
        version = platform.mac_ver()[0]
        return cls.splitVersion(version)
    
    @classmethod
    def hostOSName(cls):
        osMajor = cls.hostVersionTuple()[1]
        if osMajor <= 7:
            return u"Mac OS X"
        elif osMajor >= 12:
            return u"macOS"
        else:
            return u"OS X"
    
    @classmethod
    def getAppVersion(cls):
        bundle = NSBundle.mainBundle()
        version = bundle.objectForInfoDictionaryKey_(u"CFBundleShortVersionString")
        build = bundle.objectForInfoDictionaryKey_(u"CFBundleVersion")
        return (version, build)
    
    @classmethod
    def resolvePath_(cls, path):
        """Expand symlinks and resolve aliases."""
        def target_of_alias(path):
            url = NSURL.fileURLWithPath_(path)
            bookmarkData, error = NSURL.bookmarkDataWithContentsOfURL_error_(url, None)
            if bookmarkData is None:
                return None
            opts = NSURLBookmarkResolutionWithoutUI | NSURLBookmarkResolutionWithoutMounting
            resolved, stale, error = NSURL.URLByResolvingBookmarkData_options_relativeToURL_bookmarkDataIsStale_error_(bookmarkData, opts, None, None, None)
            return resolved.path()
        while True:
            alias_target = target_of_alias(path)
            if alias_target:
                path = alias_target
                continue
            if os.path.islink(path):
                path = os.path.realpath(path)
                continue
            return path
    
    @classmethod
    def installESDPath_(cls, path):
        u"""Resolve aliases and return path to InstallESD."""
        path = cls.resolvePath_(path)
        if not path:
            return None
        if os.path.exists(os.path.join(path,
                          u"Contents/SharedSupport/InstallESD.dmg")):
            return path
        if (os.path.basename(path).lower().startswith(u"installesd") and
            os.path.basename(path).lower().endswith(u".dmg")) and \
           os.path.exists(path):
            return path
        else:
            return None

    @classmethod
    def systemImagePath_(cls, path):
        u"""Resolve aliases and return path to a system image."""
        path = cls.resolvePath_(path)
        if not path:
            return None
        if os.path.basename(path).lower().endswith(u".dmg") and \
            os.path.exists(path):
            return path
        else:
            return None
    
    @classmethod
    def mightBeSource_(cls, path):
        if os.path.exists(os.path.join(path,
                          u"Contents/SharedSupport/InstallESD.dmg")):
            return True
        elif path.lower().endswith(u".dmg"):
            return True
        else:
            return False
    
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
        # For apps just return the size on disk.
        ext = os.path.splitext(pkgPath)[1].lower()
        if ext == u".app":
            return cls.getPackageSize_(pkgPath)
        elif ext in (u".pkg", u".mpkg"):
            # For packages first try to get the size requirements with
            # installer.
            size = cls.getInstalledPkgSizeFromInstaller_(pkgPath)
            if size is None:
                # If this fails, manually extract the size requirements from
                # the package.
                return cls.calculateInstalledPkgSize_(pkgPath)
            else:
                return size
        else:
            LogError(u"Don't know how to calculate installed size for '%@'",
                     pkgPath)
            return None
    
    @classmethod
    def getInstalledPkgSizeFromInstaller_(cls, pkgPath):
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
            LogDebug(u"/usr/sbin/installer failed to determine size requirements")
            return None
        outData = NSData.dataWithBytes_length_(out, len(out))
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(outData,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            LogError(u"Error decoding plist: %@", error)
            return None
        LogDebug(u"Installer says %@ requires %@", pkgPath, cls.formatBytes_(int(plist[u"Size"]) * 1024))
        return int(plist[u"Size"]) * 1024
    
    @classmethod
    def calculateInstalledPkgSize_(cls, pkgPath):
        if os.path.isdir(pkgPath):
            size = cls.getBundlePkgInfo_(pkgPath)
        else:
            size = cls.getFlatPkgInfo_(pkgPath)
        if size is None:
            # If all else fails, estimate package size requirements.
            LogWarning(u"Estimating package size for '%@'", pkgPath)
            size = cls.getPackageSize_(pkgPath) * 2
        LogDebug(u"%@ needs %@", pkgPath, cls.formatBytes_(size))
        return size
    
    @classmethod
    def getBundlePkgInfo_(cls, pkgPath):
        distPath = os.path.join(pkgPath, u"Contents", u"distribution.dist")
        infoPlistPath = os.path.join(pkgPath, u"Contents", u"Info.plist")
        if os.path.exists(distPath):
            return cls.getSizeFromDistribution_(distPath)
        elif os.path.exists(infoPlistPath):
            return cls.getSizeFromPkgInfoPlist_(infoPlistPath)
        else:
            LogError(u"No distribution.dist or Info.plist found in '%@'", pkgPath)
            return None
    
    @classmethod
    def getFlatPkgInfo_(cls, pkgPath):
        tempdir = tempfile.mkdtemp()
        try:
            # Extract to tempdir, excluding all except Distribution and
            # PackageInfo.
            subprocess.check_output([u"/usr/bin/xar",
                                     u"-x",
                                     u"--exclude", u"^[^DP]",
                                     u"--exclude", u"Payload",
                                     u"-C", tempdir,
                                     u"-f", pkgPath])
            distPath = os.path.join(tempdir, u"Distribution")
            pkgInfoPath = os.path.join(tempdir, u"PackageInfo")
            if os.path.exists(distPath):
                return cls.getSizeFromDistribution_(distPath)
            elif os.path.exists(pkgInfoPath):
                return cls.getSizeFromPackageInfo_(pkgInfoPath)
            else:
                LogError(u"No Distribution or PackageInfo found in '%@'", pkgPath)
                return None
        except subprocess.CalledProcessError as e:
            LogError(u"xar failed with return code %d", e.returncode)
            return None
        finally:
            try:
                shutil.rmtree(tempdir)
            except Exception as e:
                LogWarning(u"Unable to remove tempdir: %@", unicode(e))
    
    @classmethod
    def getSizeFromDistribution_(cls, distPath):
        kbytes = 0
        try:
            tree = ElementTree.parse(distPath)
            for pkgref in tree.iterfind(u"pkg-ref[@installKBytes]"):
                kbytes += int(pkgref.get(u"installKBytes"))
        except Exception as e:
            LogError(u"Failed parsing '%@': %@", distPath, unicode(e))
            return None
        return kbytes * 1024
    
    @classmethod
    def getSizeFromPackageInfo_(cls, pkgInfoPath):
        kbytes = 0
        try:
            tree = ElementTree.parse(pkgInfoPath)
            for payload in tree.iterfind(u"payload[@installKBytes]"):
                kbytes += int(payload.get(u"installKBytes"))
        except Exception as e:
            LogError(u"Failed parsing '%@': %@", pkgInfoPath, unicode(e))
            return None
        return kbytes * 1024

    @classmethod
    def getSizeFromPkgInfoPlist_(cls, infoPlistPath):
        try:
            infoDict = NSDictionary.dictionaryWithContentsOfFile_(infoPlistPath)
            return infoDict[u"IFPkgFlagInstalledSize"] * 1024
        except Exception as e:
            LogError(u"Failed parsing '%@': %@", infoPlistPath, unicode(e))
            return None

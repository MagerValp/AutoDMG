# -*- coding: utf-8 -*-
#
#  IEDUtil.py
#  AutoDMG
#
#  Created by Per Olofsson on 2013-10-31.
#  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
#

from __future__ import unicode_literals

from Foundation import *

import os.path
import subprocess
import tempfile
import shutil
import platform
from xml.etree import ElementTree
from IEDLog import LogDebug, LogInfo, LogNotice, LogWarning, LogError, LogMessage


class IEDUtil(NSObject):
    
    VERSIONPLIST_PATH = "System/Library/CoreServices/SystemVersion.plist"
    PACKAGE_EXTENSIONS = [".pkg", ".mpkg", ".app", ".dmg"]
    
    @classmethod
    def readSystemVersion_(cls, rootPath):
        """Read SystemVersion.plist on the specified volume."""
        plist = NSDictionary.dictionaryWithContentsOfFile_(os.path.join(rootPath, cls.VERSIONPLIST_PATH))
        name = plist["ProductName"]
        version = plist["ProductUserVisibleVersion"]
        build = plist["ProductBuildVersion"]
        return (name, version, build)
    
    @classmethod
    def splitVersion(cls, versionString, strip=""):
        """Split version string into a tuple of ints."""
        return tuple(int(x.strip(strip)) for x in versionString.split("."))
    
    @classmethod
    def hostVersionTuple(cls):
        version = platform.mac_ver()[0]
        return cls.splitVersion(version)
    
    @classmethod
    def hostOSName(cls):
        osMajor = cls.hostVersionTuple()[1]
        if osMajor <= 7:
            return "Mac OS X"
        elif osMajor >= 12:
            return "macOS"
        else:
            return "OS X"
    
    @classmethod
    def getAppVersion(cls):
        bundle = NSBundle.mainBundle()
        version = bundle.objectForInfoDictionaryKey_("CFBundleShortVersionString")
        build = bundle.objectForInfoDictionaryKey_("CFBundleVersion")
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
        """Resolve aliases and return path to InstallESD."""
        path = cls.resolvePath_(path)
        if not path:
            return None
        if os.path.exists(os.path.join(path,
                          "Contents/SharedSupport/InstallESD.dmg")):
            return path
        if (os.path.basename(path).lower().startswith("installesd") and
            os.path.basename(path).lower().endswith(".dmg")) and \
           os.path.exists(path):
            return path
        else:
            return None

    @classmethod
    def systemImagePath_(cls, path):
        """Resolve aliases and return path to a system image."""
        path = cls.resolvePath_(path)
        if not path:
            return None
        if os.path.basename(path).lower().endswith(".dmg") and \
            os.path.exists(path):
            return path
        else:
            return None
    
    @classmethod
    def mightBeSource_(cls, path):
        if os.path.exists(os.path.join(path,
                          "Contents/SharedSupport/InstallESD.dmg")):
            return True
        elif path.lower().endswith(".dmg"):
            return True
        else:
            return False
    
    @classmethod
    def getPackageSize_(cls, path):
        p = subprocess.Popen(["/usr/bin/du", "-sk", path],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode != 0:
            LogError("du failed with exit code %d", p.returncode)
            return 0
        else:
            return int(out.split()[0]) * 1024
    
    @classmethod
    def formatByteSize_(cls, size):
        size = float(size)
        unitIndex = 0
        while len(str(int(size))) > 3:
            size /= 1000.0
            unitIndex += 1
        return "%.1f %s" % (size, ("bytes", "kB", "MB", "GB", "TB")[unitIndex])
    
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
        if ext == ".app":
            return cls.getPackageSize_(pkgPath)
        elif ext in (".pkg", ".mpkg"):
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
            LogError("Don't know how to calculate installed size for '%@'",
                     pkgPath)
            return None
    
    @classmethod
    def getInstalledPkgSizeFromInstaller_(cls, pkgPath):
        pkgFileName = os.path.os.path.basename(pkgPath)
        tempdir = tempfile.mkdtemp()
        try:
            symlinkPath = os.path.join(tempdir, pkgFileName)
            os.symlink(pkgPath, symlinkPath)
            p = subprocess.Popen(["/usr/sbin/installer",
                                  "-pkginfo",
                                  "-verbose",
                                  "-plist",
                                  "-pkg",
                                  symlinkPath],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            out, err = p.communicate()
        finally:
            try:
                shutil.rmtree(tempdir)
            except BaseException as e:
                LogWarning("Unable to remove tempdir: %@", str(e))
        if p.returncode != 0:
            LogDebug("/usr/sbin/installer failed to determine size requirements")
            return None
        outData = NSData.dataWithBytes_length_(out, len(out))
        plist, format, error = NSPropertyListSerialization.propertyListWithData_options_format_error_(outData,
                                                                                                      NSPropertyListImmutable,
                                                                                                      None,
                                                                                                      None)
        if not plist:
            LogError("Error decoding plist: %@", error)
            return None
        LogDebug("Installer says %@ requires %@", pkgPath, cls.formatByteSize_(int(plist["Size"]) * 1024))
        return int(plist["Size"]) * 1024
    
    @classmethod
    def calculateInstalledPkgSize_(cls, pkgPath):
        if os.path.isdir(pkgPath):
            size = cls.getBundlePkgInfo_(pkgPath)
        else:
            size = cls.getFlatPkgInfo_(pkgPath)
        if size is None:
            # If all else fails, estimate package size requirements.
            LogWarning("Estimating package size for '%@'", pkgPath)
            size = cls.getPackageSize_(pkgPath) * 2
        LogDebug("%@ needs %@", pkgPath, cls.formatByteSize_(size))
        return size
    
    @classmethod
    def getBundlePkgInfo_(cls, pkgPath):
        distPath = os.path.join(pkgPath, "Contents", "distribution.dist")
        infoPlistPath = os.path.join(pkgPath, "Contents", "Info.plist")
        if os.path.exists(distPath):
            return cls.getSizeFromDistribution_(distPath)
        elif os.path.exists(infoPlistPath):
            return cls.getSizeFromPkgInfoPlist_(infoPlistPath)
        else:
            LogError("No distribution.dist or Info.plist found in '%@'", pkgPath)
            return None
    
    @classmethod
    def getFlatPkgInfo_(cls, pkgPath):
        tempdir = tempfile.mkdtemp()
        try:
            # Extract to tempdir, excluding all except Distribution and
            # PackageInfo.
            subprocess.check_output(["/usr/bin/xar",
                                     "-x",
                                     "--exclude", "^[^DP]",
                                     "--exclude", "Payload",
                                     "-C", tempdir,
                                     "-f", pkgPath])
            distPath = os.path.join(tempdir, "Distribution")
            pkgInfoPath = os.path.join(tempdir, "PackageInfo")
            if os.path.exists(distPath):
                return cls.getSizeFromDistribution_(distPath)
            elif os.path.exists(pkgInfoPath):
                return cls.getSizeFromPackageInfo_(pkgInfoPath)
            else:
                LogError("No Distribution or PackageInfo found in '%@'", pkgPath)
                return None
        except subprocess.CalledProcessError as e:
            LogError("xar failed with return code %d", e.returncode)
            return None
        finally:
            try:
                shutil.rmtree(tempdir)
            except Exception as e:
                LogWarning("Unable to remove tempdir: %@", str(e))
    
    @classmethod
    def getSizeFromDistribution_(cls, distPath):
        kbytes = 0
        try:
            tree = ElementTree.parse(distPath)
            for pkgref in tree.iterfind("pkg-ref[@installKBytes]"):
                kbytes += int(pkgref.get("installKBytes"))
        except Exception as e:
            LogError("Failed parsing '%@': %@", distPath, str(e))
            return None
        return kbytes * 1024
    
    @classmethod
    def getSizeFromPackageInfo_(cls, pkgInfoPath):
        kbytes = 0
        try:
            tree = ElementTree.parse(pkgInfoPath)
            for payload in tree.iterfind("payload[@installKBytes]"):
                kbytes += int(payload.get("installKBytes"))
        except Exception as e:
            LogError("Failed parsing '%@': %@", pkgInfoPath, str(e))
            return None
        return kbytes * 1024

    @classmethod
    def getSizeFromPkgInfoPlist_(cls, infoPlistPath):
        try:
            infoDict = NSDictionary.dictionaryWithContentsOfFile_(infoPlistPath)
            return infoDict["IFPkgFlagInstalledSize"] * 1024
        except Exception as e:
            LogError("Failed parsing '%@': %@", infoPlistPath, str(e))
            return None

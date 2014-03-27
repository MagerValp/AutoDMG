//
//  IEDMountInfo.m
//  AutoDMG
//
//  Created by Per Olofsson on 2014-03-26.
//  Copyright 2013-2014 Per Olofsson, University of Gothenburg. All rights reserved.
//

#include <sys/param.h>
#include <sys/mount.h>
#import "IEDMountInfo.h"

@implementation IEDMountInfo

+ (NSDictionary *)getMountPoints
{
    struct statfs *mntbuf;
    int mntsize;
    
    if ((mntsize = getmntinfo(&mntbuf, MNT_NOWAIT)) == 0) {
        NSLog(@"getmntinfo failed");
        return NULL;
    }
    NSMutableDictionary *mountPoints = [[NSMutableDictionary alloc] init];
    for (int i = 0; i < mntsize; i++) {
//        NSLog(@"f_mntonname: %s (%s, %s)",
//               mntbuf[i].f_mntonname,
//               mntbuf[i].f_fstypename,
//               mntbuf[i].f_flags & MNT_LOCAL ? "local" : "remote");
        NSString *mntonname = [NSString stringWithUTF8String:mntbuf[i].f_mntonname];
        NSString *fstypename = [NSString stringWithUTF8String:mntbuf[i].f_fstypename];
        mountPoints[mntonname] = @{@"fstypename": fstypename,
                                   @"islocal": mntbuf[i].f_flags & MNT_LOCAL ? @true : @false};
    }
    return mountPoints;
}

@end

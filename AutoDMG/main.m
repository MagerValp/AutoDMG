//
//  main.m
//  AutoDMG
//
//  Created by Per Olofsson on 2013-09-19.
//  Copyright 2013-2014 Per Olofsson, University of Gothenburg. All rights reserved.
//

#import <Cocoa/Cocoa.h>
#import <Python/Python.h>


int main(int argc, const char *argv[])
{
    int result;
    
    @autoreleasepool {

        NSBundle *mainBundle = [NSBundle mainBundle];
        NSString *resourcePath = [mainBundle resourcePath];
        NSArray *pythonPathArray = @[resourcePath, [resourcePath stringByAppendingPathComponent:@"PyObjC"]];
        
        setenv("PYTHONPATH", [[pythonPathArray componentsJoinedByString:@":"] UTF8String], 1);
        
        NSArray *possibleMainExtensions = @[@"py", @"pyc", @"pyo"];
        NSString *mainFilePath = nil;
        
        for (NSString *possibleMainExtension in possibleMainExtensions) {
            mainFilePath = [mainBundle pathForResource:@"main" ofType:possibleMainExtension];
            if (mainFilePath) {
                break;
            }
        }
        if (!mainFilePath) {
            [NSException raise:NSInternalInconsistencyException format:@"%s:%d main() Failed to find the main.{py,pyc,pyo} file in the application wrapper's Resources directory.", __FILE__, __LINE__];
        }
        
        Py_SetProgramName("/usr/bin/python");
        Py_Initialize();
        PySys_SetArgv(argc, (char **)argv);
        
        const char *mainFilePathPtr = [mainFilePath UTF8String];
        FILE *mainFile = fopen(mainFilePathPtr, "r");
        result = PyRun_SimpleFile(mainFile, (char *)[[mainFilePath lastPathComponent] UTF8String]);
        
        if (result != 0) {
            [NSException raise:NSInternalInconsistencyException
                        format:@"%s:%d main() PyRun_SimpleFile failed with file '%@', see console for errors.", __FILE__, __LINE__, mainFilePath];
        }
    
    }

    return result;
}

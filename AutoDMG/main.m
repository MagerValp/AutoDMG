//
//  main.m
//  AutoDMG
//
//  Created by Per Olofsson on 2013-09-19.
//  Copyright 2013-2016 Per Olofsson, University of Gothenburg. All rights reserved.
//

#import <Cocoa/Cocoa.h>
#import <Python/Python.h>
#import <ExceptionHandling/ExceptionHandling.h>


int gSysExit;

void checkSysExit(void)
{
    if (gSysExit) {
        NSLog(@"Application terminated with exit()");
    }
}


void exceptionHandler(NSException *exception)
{
    NSLog(@"UncaughtExceptionHandler:");
    NSLog(@"%@", [exception reason]);
    NSLog(@"User info: %@", [exception userInfo]);
    NSLog(@"Strack trace: %@", [[exception userInfo] objectForKey:NSStackTraceKey]);
}


int main(int argc, const char *argv[])
{
    int result;
    
    gSysExit = 1;
    atexit(checkSysExit);
    
    NSSetUncaughtExceptionHandler(&exceptionHandler);
    
    @autoreleasepool {
        
        // Initialize Python interpreter.
        Py_SetProgramName("/usr/bin/python");
        Py_Initialize();
        PySys_SetArgvEx(argc, (char **)argv, 0);
        PyObject *pSysPath = PySys_GetObject("path");
        PyObject *pResourcePath = PyString_FromString([[[NSBundle mainBundle] resourcePath] UTF8String]);
        if (PyList_Insert(pSysPath, 0, pResourcePath) == -1) {
            PyErr_Print();
            [NSException raise:NSInternalInconsistencyException format:@"Couldn't add '%@' to sys.path", [[NSBundle mainBundle] resourcePath]];
        }
        
        // Import main.py from Resources.
        PyObject *pName = PyString_FromString("main");
        PyObject *pModule = PyImport_Import(pName);
        Py_DECREF(pName);
        if (!pModule) {
            PyErr_Print();
            [NSException raise:NSInternalInconsistencyException format:@"Import of main.py failed"];
        }
        
        // Find the function main().
        PyObject *pFunc = PyObject_GetAttrString(pModule, "main");
        if (!pFunc) {
            if (PyErr_Occurred()) {
                PyErr_Print();
            }
            Py_DECREF(pModule);
            [NSException raise:NSInternalInconsistencyException format:@"Can't find function main() in main.py"];
        }
        if (!PyCallable_Check(pFunc)) {
            Py_DECREF(pFunc);
            Py_DECREF(pModule);
            [NSException raise:NSInternalInconsistencyException format:@"main isn't callable in main.py"];
        }
        
        // Call main().
        PyObject *pValue = PyObject_CallObject(pFunc, NULL);
        // NB: If NSApplicationMain() is called in the Python script the code below this point will never execute.
        Py_DECREF(pFunc);
        if (!pValue) {
            PyErr_Print();
            Py_DECREF(pModule);
            [NSException raise:NSInternalInconsistencyException format:@"Call to main() in main.py failed"];
        }
        
        // Use the returned value as our exit status.
        result = (int)PyInt_AsLong(pValue);
        
        Py_DECREF(pValue);
        Py_DECREF(pModule);
        
        Py_Finalize();
    
    }
    
    gSysExit = 0;
    return result;
}

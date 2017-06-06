AutoDMG
=======

The award winning AutoDMG takes a macOS installer (10.10 or newer) and builds a system image suitable for deployment with Imagr, DeployStudio, LANrev, Jamf Pro, and other asr-based imaging tools.

![Autodmg 1.7.1](https://magervalp.github.io/images/AutoDMG-1.7.1.png)


Documentation
-------------

Documentation and help is in the [AutoDMG wiki](https://github.com/MagerValp/AutoDMG/wiki).


Presentation
------------

For a great overview of modular imaging and a demonstration of some of AutoDMG's features, watch Anthony Reimer's presentation from Penn State MacAdmins 2014:

[![Modular Image Creation](http://img.youtube.com/vi/VQXhTPsUlzI/0.jpg)](http://www.youtube.com/watch?v=VQXhTPsUlzI)


Download
--------

The latest release can be found on the [release page](https://github.com/MagerValp/AutoDMG/releases).


Support
-------

If you have questions or need help, you can join us in [`#autodmg`](https://macadmins.slack.com/archives/autodmg) on [Slack MacAdmins](http://macadmins.org ).

If you find a bug, please report it in the [issue tracker](https://github.com/MagerValp/AutoDMG/issues).


License
-------

    Copyright 2013-2017 Per Olofsson, University of Gothenburg. All rights reserved.
    
    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at
    
        http://www.apache.org/licenses/LICENSE-2.0
    
    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

AutoDMG uses [STPrivilegedTask](https://github.com/sveinbjornt/STPrivilegedTask),
an NSTask-like wrapper around AuthorizationExecuteWithPrivileges.
Copyright &copy; 2009-2016 Sveinbjörn Þórðarson <sveinbjornt@gmail.com>

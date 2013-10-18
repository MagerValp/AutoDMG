#!/bin/sh

#  test.sh
#  InstallESDtoDMG
#
#  Created by Per Olofsson on 2013-09-24.
#  Copyright (c) 2013 University of Gothenburg. All rights reserved.

logger -t test "* test.sh starting"

echo "IED:MSG:Starting test script"
sleep 2

echo 'installer: Package name is create_createduser-1.0'
echo 'installer: Installing at base path /'
echo 'installer:PHASE:Förbereder installation…'
sleep 0.25
echo 'installer:PHASE:Förbereder skivan…'
sleep 0.1
echo 'installer:PHASE:Förbereder create_createduser-1.0…'
sleep 0.1
echo 'installer:PHASE:Väntar på att andra installationer ska avslutas…'
echo 'installer:PHASE:Anpassar installationen…'
sleep 0.1
echo 'installer:STATUS:'
echo 'installer:%25.686066'
sleep 0.25
echo 'installer:STATUS:'
echo 'installer:%50.13'
sleep 0.25
echo 'installer:STATUS:'
echo 'installer:%75.686066'
sleep 0.25
echo 'installer:PHASE:Rensar…'
sleep 0.25
echo 'installer:PHASE:Kontrollerar paket…'
sleep 0.25
echo 'installer:%97.750000'
sleep 0.25
echo 'installer:STATUS:'
echo 'installer:PHASE:Avslutar installationen…'
sleep 0.25
echo 'installer:STATUS:'
echo 'installer:%100.000000'
sleep 0.25
echo 'installer:PHASE:Programvaran har installerats.'
echo 'installer: The install was successful.'

echo "IED:SUCCESS:Testing successful"

logger -t test "* test.sh done"

exit 0

#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import argparse
import argcomplete

import subprocess

from novalabs.core.CoreConsole import *
import yaml

# ENVIRONMENT VARIABLES -------------------------------------------------------

NOVA_WORKSPACE_ROOT = os.environ.get("NOVA_WORKSPACE_ROOT")
if NOVA_WORKSPACE_ROOT is None:
    CoreConsole.out(CoreConsole.error("NOVA_WORKSPACE_ROOT environment variable not found"))
    sys.exit(-1)

stream = open(os.path.join(NOVA_WORKSPACE_ROOT, "deploy.yml"), 'r')

data = yaml.load(stream)

print('#!/bin/bash')

deploy_dir = os.path.join(NOVA_WORKSPACE_ROOT, 'build', 'deploy')
print('LOGFILE=' + os.path.join(deploy_dir, "log.txt"))

print('rm -rf ' + deploy_dir)
print('mkdir -p ' + deploy_dir)

print('FAIL=0')

for target in data:
    types = data[target]['type']
    for type in types:
        print('DIRECTORY=' + os.path.join(NOVA_WORKSPACE_ROOT, 'build', type[0], target))
        print('if [ -d "$DIRECTORY" ]; then')
        print('  cd $DIRECTORY')
        #print('  make clean')
        print('  make deploy')
        print('  if [ $? -eq 0 ]; then')
        print('    echo BUILT $DIRECTORY >> $LOGFILE')
        print('  else')
        print('    FAIL=-1')
        print('    echo ERROR $DIRECTORY >> $LOGFILE')
        print('  fi')
        for fmt in type[1]:
            print('  cp ' + os.path.join(NOVA_WORKSPACE_ROOT, 'build', type[0], target, '*.' + fmt) + ' ' + deploy_dir + '/')
        print('  cp ' + os.path.join(NOVA_WORKSPACE_ROOT, 'build', type[0], target, '*.crc') + ' ' + deploy_dir + '/' + ' || :')
        print('  cp ' + os.path.join(NOVA_WORKSPACE_ROOT, 'build', type[0], target, '*.revision') + ' ' + deploy_dir + '/' + ' || :')
        print('else')
        print('  echo $DIRECTORY does not exists >> $LOGFILE')
        print('  FAIL=-1')
        print('fi')

print('cd ' + os.path.join(NOVA_WORKSPACE_ROOT))

print('exit $FAIL')

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
from novalabs.misc.helpers import *
from novalabs.misc.crc import *
import yaml

# ENVIRONMENT VARIABLES -------------------------------------------------------

NOVA_WORKSPACE_ROOT = os.environ.get("NOVA_WORKSPACE_ROOT")
if NOVA_WORKSPACE_ROOT is None:
    CoreConsole.out(CoreConsole.error("NOVA_WORKSPACE_ROOT environment variable not found"))
    sys.exit(-1)

def process(device_type, program, filename, device):
    try:
        src = open(os.path.join(NOVA_WORKSPACE_ROOT, "build", "deploy", program) + ".revision")
        revision = src.read()
        revision = revision.rstrip()
        src.close
        
        src = open(os.path.join(NOVA_WORKSPACE_ROOT, "fwu", "templates", device_type) + ".header")
        header = src.read()
        src.close()
        
        src = open(os.path.join(NOVA_WORKSPACE_ROOT, "build", "deploy", program) + "_" + revision + ".crc")
        crc = src.read()
        crc = crc.rstrip()
        src.close()

        src = open(os.path.join(NOVA_WORKSPACE_ROOT, "build", "deploy", program) + "_" + revision + ".hex")
        program = src.read()
        src.close()

        header = header.replace("@REVISION@", revision)
        header = header.replace("@FILENAME@", filename + ".fwu")
        header = header.replace("@NAME@", device)
        header = header.replace("@CRC@", crc)

        fwu_filename = os.path.join(NOVA_WORKSPACE_ROOT, "fwu", "out", filename) + "_" + revision + ".fwu"

        fwu = open(fwu_filename, 'w')

        fwu.write(header)

        fwu.write("#------------------------------------------\n");
        fwu.write("!BEGIN_PROGRAM\n");
        fwu.write("#------------------------------------------\n");

        fwu.write(program)

        fwu.write("#------------------------------------------\n");
        fwu.write("!END_PROGRAM\n");
        fwu.write("#------------------------------------------\n");
        
        fwu.close()
        
        fwu = open(fwu_filename, 'rb')
        data = fwu.read()
        fwu.close()
        
        d = 4 - (len(data) % 4)
        
        if d == 4:
            d = 0;
        
        data = bytearray(data)
        
        for i in range(0, d):
            data.append(0);
            
        file_crc = stm32_crc32_bytes(0xffffffff, data)
        file_crc = bytearray("@CRC:" + hex(file_crc) +"\n", 'ascii')
        
        fwu = open(fwu_filename, 'wb')
        fwu.write(file_crc);
        fwu.write(data);
        fwu.close()
        
        CoreConsole.out(Fore.YELLOW + Style.BRIGHT + device_type + Fore.BLUE + "." + device + Style.RESET_ALL + " -> " + Style.BRIGHT + filename + "_" + revision + ".fwu" + Style.RESET_ALL)
    except IOError as e:
        CoreConsole.out(CoreConsole.error(str(e)))

stream = open(os.path.join(NOVA_WORKSPACE_ROOT, "fwu.yml"), 'r')

data = yaml.load(stream)

for device_type in data:
    program = data[device_type]['program']
    for target in data[device_type]['targets']:
        for filename, v in target.items():
            device = v['device']
            process(device_type, program, filename, device)


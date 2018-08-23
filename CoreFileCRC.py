#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import sys, os, threading, struct
import logging
import argparse

from novalabs.misc.helpers import *
from novalabs.misc.crc import *

from time import sleep

# ==============================================================================

def _create_argsparser():
    parser = argparse.ArgumentParser(
        description='CoreFileCRC'
    )

    parser.add_argument(
        '-v', '--verbose', required=False, action='count', default=0,
        help='verbosity level (default %(default)s): 0=critical, 1=error, 2=warning, 3=info, 4=debug',
        dest='verbosity'
    )

    parser.add_argument(
        '-i', '--interactive', required=False,
        action="store_true",
        default=False,
        help='Interactive mode',
        dest='interactive'
    )


    parser.add_argument('file', nargs=1, help="FILE", default=None)

    return parser


# ==============================================================================


def file_crc(args):
    try:
        in_file = open(args.file[0], 'rb')
    except IOError:
        sys.stderr.write("error: can't open file.\n")
        return -1;

    data = in_file.read()
    d = 4 - (len(data) % 4)
    
    if d == 4:
        d = 0;
    
    data = bytearray(data)
    
    #print(len(data))

    for i in range(0, d):
        data.append(0);
        
    #print(len(data))
    
    crc = stm32_crc32_bytes(0xffffffff, data)

    print("@CRC:" + hex(crc))

    return 0

def _main():
    parser = _create_argsparser()
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stderr, level=verbosity2level(int(args.verbosity)))
    logging.debug('sys.argv = ' + repr(sys.argv))

    retval = file_crc(args)
    
    sys.exit(retval)

if __name__ == '__main__':
    try:
        _main()
    except Exception as e:
        raise

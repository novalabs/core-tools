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
        description='CoreHexCRC'
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
    parser.add_argument('size', nargs=1, help="SIZE", default=None)

    return parser


# ==============================================================================


def hex_crc(args):
    ihex_file = args.file[0]
    programSize = int(args.size[0])

    from intelhex import IntelHex

    ih = IntelHex()
    ih.loadfile(ihex_file, format="hex")
    ih.padding = 0xFF
    bin = ih.tobinarray(size=programSize)
    crc = stm32_crc32_bytes(0xffffffff, bin)
    print(hex(crc))

    return 0

def _main():
    parser = _create_argsparser()
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stderr, level=verbosity2level(int(args.verbosity)))
    logging.debug('sys.argv = ' + repr(sys.argv))

    retval = hex_crc(args)
    
    sys.exit(retval)

if __name__ == '__main__':
    try:
        _main()
    except Exception as e:
        raise

#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import sys, os, threading, struct
import logging
import argparse

import novalabs.core.MW as MW
from novalabs.misc.helpers import *
from novalabs.misc.crc import *

from time import sleep


# ==============================================================================

def load_completer(prefix, parsed_args, **kwargs):
    mm = ["program", "configuration"]
    return (m for m in mm if m.startswith(prefix))


def erase_completer(prefix, parsed_args, **kwargs):
    mm = ["program", "configuration", "user", "all"]
    return (m for m in mm if m.startswith(prefix))


def _create_argsparser():
    parser = argparse.ArgumentParser(
        description='R2P set app parameter'
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

    tgroup = parser.add_argument_group('transport setup')
    tgroup.add_argument(
        '-p', '--transport', required=False, nargs='+',
        default=['DebugTransport', 'SerialLineIO', '/dev/ttyUSB0', 921600],  # 921600
        help='transport parameters',
        dest='transport', metavar='PARAMS'
    )

    subparsers = parser.add_subparsers(help='Sub command help', dest='action')

    parser_ls = subparsers.add_parser('ls', help='Lists the Modules')

    parser_boot = subparsers.add_parser('boot', help='Ask the modules (at boot) to go into bootloader mode')

    parser_id = subparsers.add_parser('identify', help='Identify a Module')
    parser_id.add_argument('uid', nargs=1, help="UID", default=None)

    parser_describe = subparsers.add_parser('describe', help='Describe a Module')
    parser_describe.add_argument('uid', nargs='*', help="UID", default=None)

    # parser_select = subparsers.add_parser('select', help='Selects a Module')
    # parser_select.add_argument('uid', nargs=1, help="UID", default=None)

    # parser_deselect = subparsers.add_parser('deselect', help='Deselects a Module')
    # parser_deselect.add_argument('uid', nargs=1, help="UID", default=None)

    parser_reset = subparsers.add_parser('reset', help='Resets a Module')
    parser_reset.add_argument('uid', nargs=1, help="UID", default=None)

    parser_reset = subparsers.add_parser('load', help='Load a FW')
    parser_reset.add_argument('what', nargs=1, help="[program|configuration]", default='program').completer = load_completer
    parser_reset.add_argument('uid', nargs=1, help="UID", default=None)
    parser_reset.add_argument('file', nargs=1, help="FILE", default=None)

    parser_erase_config = subparsers.add_parser('erase', help='Erases something')
    parser_erase_config.add_argument('what', nargs=1, help="[program|configuration|all]", default='program').completer = erase_completer
    parser_erase_config.add_argument('uid', nargs=1, help="UID", default=None)

    parser_write_name = subparsers.add_parser('name', help='Write the module name')
    parser_write_name.add_argument('uid', nargs=1, help="UID", default=None)
    parser_write_name.add_argument('name', nargs=1, help="NAME", default=None)

    parser_write_name = subparsers.add_parser('id', help='Write the module name')
    parser_write_name.add_argument('uid', nargs=1, help="UID", default=None)
    parser_write_name.add_argument('id', nargs=1, help="ID", default=None)

    parser_read = subparsers.add_parser('read', help='Write the module name')
    parser_read.add_argument('uid', nargs=1, help="UID", default=None)
    parser_read.add_argument('address', nargs=1, help="ADDRESS", default=None)

    return parser


# ==============================================================================

def hexdump_list(l):
    return (''.join(format(x, '02x') for x in l))


def boot(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    bl.deselect(0)

    while MW.ok():
        sleep(0.25)
        bl.bootload()

    bl.stop()

    return 0


def ls(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)
    if args.interactive:
        while MW.ok():
            print("------------------------")
            for k in bl.getSlaves():
                print(("%08X" % k) + ', ' + bl._slavesTypes[k] + ', ' + bl._slavesNames[k])
                pass

            bl.clear()
            sleep(2)
    else:
        sleep(3)
        for k in bl.getSlaves():
            print("%08X" % k)

    bl.stop()

    return 0


def identify(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])

    retval = 1

    if bl.identify(uid):
        retval = 0

    bl.stop()

    return retval


def formatDescription(uid, desc):
    if desc is not None:
        return "%08X, %d, %d, %s, %d, %s" % (uid, desc.program, desc.user, str(desc.module_type, "ascii"), desc.can_id, str(desc.module_name, "ascii"))
    else:
        return None


def describe(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()

    retval = 0

    if len(args.uid) == 1:
        sleep(1)
        uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])

        if not bl.select(uid):
            print("Cannot select device")
            return 1

        desc = bl.describe(uid)
        if desc is None:
            retval = 1
        else:
            print(formatDescription(uid, desc))

        if not bl.deselect(uid):
            print("Cannot deselect device")
            retval = 1

    else:
        sleep(3)

        uids = bl.getSlaves()

        for k in uids:
            uid = k
            if not bl.select(uid):
                print("Cannot select device")
                return 1

            desc = bl.describe(uid)
            if desc is None:
                retval = 1
            else:
                print(formatDescription(uid, desc))

            if not bl.deselect(uid):
                print("Cannot deselect device")
                retval = 1
    bl.stop()

    return retval


def select(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])

    retval = 0

    if not bl.select(uid):
        print("Cannot select device")
        retval = 1

    bl.stop()

    return retval


def deselect(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])

    retval = 0

    if not bl.deselect(uid):
        print("Cannot deselect device")
        retval = 1

    bl.stop()

    return retval


def erase(mw, transport, args):
    what = args.what[0]

    if what == 'program':
        pass
    elif what == 'user':
        pass
    elif what == 'configuration':
        pass
    elif what == 'all':
        pass
    else:
        print("Erase what?")
        return 1

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])

    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    retval = 0

    if not bl.select(uid):
        print("Cannot select device")
        return 1

    what = args.what[0]

    if what == 'program':
        if not bl.eraseProgram(uid):
            print("Cannot erase program")
            retval = 2

    if what == 'user':
        if not bl.eraseUserConfiguration(uid):
            print("Cannot erase user configuration")
            retval = 2

    if what == 'configuration':
        if not bl.eraseConfiguration(uid):
            print("Cannot erase user configuration")
            retval = 2

    if what == 'all':
        if not bl.eraseConfiguration(uid):
            print("Cannot erase configuration")
            retval = 2
        if not bl.eraseProgram(uid):
            print("Cannot erase program")
            retval = 2

    if not bl.deselect(uid):
        print("Cannot deselect device")
        retval = 1

    bl.stop()

    return retval


def reset(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])

    retval = 0

    if not bl.select(uid):
        print("Cannot select device")
        return 1

    if not bl.reset(uid):
        retval = 1

    bl.deselect(0)

    bl.stop()

    return retval


def load(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    retval = 1

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])
    ihex_file = args.file[0]

    if not uid in bl.getSlaves():
        print("Device is not in bootload mode")
        return 1

    programSize = bl.getSlavesProgramStorageSize(uid)
    print(programSize)
    from intelhex import IntelHex

    ih = IntelHex()
    ih.loadfile(ihex_file, format="hex")
    ih.padding = 0xFF
    bin = ih.tobinarray(size=programSize)
    crc = stm32_crc32_bytes(0xffffffff, bin)
    print(hex(crc))

    if not bl.select(uid):
        print("Cannot select device")
        return 1

    what = args.what[0]
    if what == 'program':
        if not bl.eraseProgram(uid):
            print("Cannot erase program")
            return 1

    with open(ihex_file) as f:
        data = f.read().splitlines()

    type = MW.BootMsg.IHEX.IHexTypeEnum.BEGIN
    if not bl.ihex_write(type, ""):
        print("Cannot write IHEX data")
        return 1

    l = 0
    for line in data:
        type = MW.BootMsg.IHEX.IHexTypeEnum.DATA
        print("%d of %d" % (l, len(data)))

        l += 1

        print(line)

        if not bl.ihex_write(type, line):
            print("Cannot write IHEX data")
            return 1

    type = MW.BootMsg.IHEX.IHexTypeEnum.END
    if not bl.ihex_write(type, ""):
        print("Cannot write IHEX data")
        return 1

    if what == 'program':
        if not bl.write_program_crc(uid, crc):
            print("Cannot write CRC")
            return 1

    bl.deselect(uid)

    bl.stop()

    return retval


def name(mw, transport, args):
    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])
    name = args.name[0]

    if len(name) > 16:
        print("Name must be at most 16 bytes long")
        return 1

    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    retval = 0

    if not bl.select(uid):
        print("Cannot select device")
        retval = 1

    if not bl.write_name(uid, name):
        print("Cannot write module name")
        retval = 1

    if not bl.deselect(uid):
        print("Cannot deselect device")
        retval = 1

    bl.stop()

    return retval


def moduleid(mw, transport, args):
    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])
    id = int(args.id[0])

    if id > 126:
        print("ID must be <= 126    ")
        return 1

    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    retval = 0

    if not bl.select(uid):
        print("Cannot select device")
        retval = 1

    if not bl.write_id(uid, id):
        print("Cannot write module id")
        retval = 1

    if not bl.deselect(uid):
        print("Cannot deselect device")
        retval = 1

    bl.stop()

    return retval


def read(mw, transport, args):
    bl = MW.Bootloader()
    bl.start()
    sleep(1)

    retval = 1

    uid = MW.BootMsg.UID.getUIDFromHexString(args.uid[0])
    #    address = 0x08000000 + 20480 + 2048 +2048
    address = int(args.address[0])

    if not bl.select(uid):
        print("Cannot select device")
        return 1

    if not bl.ihex_read(uid, address):
        print("Cannot write module name")
        return 1

    bl.deselect(uid)

    #    bl.select("000000000000000000000000")
    #    if not bl.deselect(uid):
    #        print("Cannot deselect device")
    #        return 1


    bl.stop()

    return retval


def _main():
    parser = _create_argsparser()
    args = parser.parse_args()

    logging.basicConfig(stream=sys.stderr, level=verbosity2level(int(args.verbosity)))
    logging.debug('sys.argv = ' + repr(sys.argv))

    # TODO: Automate transport construction from "--transport" args
    assert args.transport[0] == 'DebugTransport'
    assert args.transport[1] == 'SerialLineIO'
    lineio = MW.SerialLineIO(str(args.transport[2]), int(args.transport[3]))
    transport = MW.DebugTransport('dbgtra', lineio)

    mw = MW.Middleware.instance()
    mw.initialize()
    transport.open()

    if args.action == 'boot':
        retval = boot(mw, transport, args)

    if args.action == 'ls':
        retval = ls(mw, transport, args)

    if args.action == 'identify':
        retval = identify(mw, transport, args)

    # if args.action == 'select':
    #    retval = select(mw, transport, args)

    # if args.action == 'deselect':
    #    retval = deselect(mw, transport, args)

    if args.action == 'reset':
        retval = reset(mw, transport, args)

    if args.action == 'load':
        retval = load(mw, transport, args)

    if args.action == 'erase':
        retval = erase(mw, transport, args)

    if args.action == 'name':
        retval = name(mw, transport, args)

    if args.action == 'id':
        retval = moduleid(mw, transport, args)

    if args.action == 'describe':
        retval = describe(mw, transport, args)

    if args.action == 'read':
        retval = read(mw, transport, args)

    mw.uninitialize()
    transport.close()

    sys.exit(retval)


if __name__ == '__main__':
    try:
        _main()
    except Exception as e:
        raise

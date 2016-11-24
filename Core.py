#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import argcomplete
import argparse

from novalabs.core.Core import *


def action_completer(prefix, parsed_args, **kwargs):
    mm = ["ls"]
    return (m for m in mm if m.startswith(prefix))


def ls(srcPath, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    core = Core()
    core.open(srcPath)

    CoreConsole.out(CoreConsole.h1("CORE"))

    table = []
    if core.valid:
        table.append([CoreConsole.highlight(core.name), core.description, core.root])
        CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "Root"]))
    else:
        CoreConsole.out(CoreConsole.error(core.reason))

    if not core.valid:
        return -1

    isOk = True

    table = []
    core.openPackages()

    for package in core.validPackages:
        table.append(package.getSummary(core.root))

    for package in core.invalidPackages:
        table.append(package.getSummary(core.root))
        isOk = False

    if (len(core.validPackages) + len(core.invalidPackages)) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGES"))
        CoreConsole.out(CoreConsole.table(table, CorePackage.getSummaryFields()))

    table = []
    core.openModules()

    for module in core.validModules:
        table.append(module.getSummary(core.root))

    for module in core.invalidModules:
        table.append(module.getSummary(core.root))
        isOk = False

    if (len(core.validModules) + len(core.invalidModules)) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MODULES"))
        CoreConsole.out(CoreConsole.table(table, CoreModule.getSummaryFields()))

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1

def update(srcPath, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    core = Core()
    core.open(srcPath)

    CoreConsole.out(CoreConsole.h1("CORE"))

    table = []
    if core.valid:
        table.append([CoreConsole.highlight(core.name), core.description, core.root])
        CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "Root"]))
    else:
        CoreConsole.out(CoreConsole.error(core.reason))

    if not core.valid:
        return -1

    isOk = True

    isOk = UpdateCore(core.getRoot())

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


if '__main__' == __name__:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", help="Verbose output [default = False]", action="store_true", default=False)
        subparsers = parser.add_subparsers(help='Sub command help', dest='action')

        parser_ls = subparsers.add_parser('ls', help='Lists the Core distribution contents')
        parser_ls.add_argument("path", nargs='?', help="Path to Core [default = None]", default=None)

        parser_update = subparsers.add_parser('update', help='Update')
        parser_update.add_argument("path", nargs='?', help="Path to Core [default = None]", default=None)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        retval = 0

        if args.action == "ls":
            src = args.path

            if src is not None:
                if src == ".":
                    src = None
            else:
                coreRoot = os.environ.get("NOVA_CORE_ROOT")
                if coreRoot is None:
                    CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
                    sys.exit(-1)
                src = coreRoot

            retval = ls(src, args.verbose)

        if args.action == "update":
            src = args.path

            if src is not None:
                if src == ".":
                    src = None
            else:
                coreRoot = os.environ.get("NOVA_CORE_ROOT")
                if coreRoot is None:
                    CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
                    sys.exit(-1)
                src = coreRoot

            retval = update(src, args.verbose)

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1)

#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import argcomplete
import argparse
import shutil

from novalabs.core.CoreModule import *


def action_completer(prefix, parsed_args, **kwargs):
    mm = ["ls", "clean", "generate"]
    return (m for m in mm if m.startswith(prefix))


def module_completer(prefix, parsed_args, **kwargs):
    if parsed_args.action is not None:
        coreRoot = os.environ.get("NOVA_CORE_ROOT")
        if coreRoot is not None:
            mm = listDirectories(os.path.join(coreRoot, "modules"))  # TODO ...
            return (m for m in mm if m.startswith(prefix))


def ls(srcPath, workspaceMode, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    p = CoreModule()
    p.open(srcPath)

    table = [p.getSummary(coreRoot)]
    CoreConsole.out(CoreConsole.h1("MODULE"))
    CoreConsole.out(CoreConsole.table(table, CoreModule.getSummaryFields()))

    if not p.valid:
        isOk = False

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def generate(srcPath, dstPath, workspaceMode, verbose, link=False, relPathSrc=None, relPathDst=None):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    module = CoreModule()
    module.open(srcPath)

    if not module.valid:
        printSuccessOrFailure(False)
        return -1

    isOk = True

    table = []

    targetPath = dstPath

    if workspaceMode:
        isOk = module.generate(targetPath, "${WORKSPACE_MODULES_PATH}", link=link)
    else:
        isOk = module.generate(targetPath, link=link)

    table = [module.getSummaryGenerate(relPathSrc, relPathDst)]
    CoreConsole.out(CoreConsole.h1("MODULE"))
    CoreConsole.out(CoreConsole.table(table, CoreModule.getSummaryFieldsGenerate()))

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


if '__main__' == __name__:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", help="Verbose output [default = False]", action="store_true", default=False)
        parser.add_argument("--no-workspace", help="No Workspace mode", action="store_false", default=True)
        subparsers = parser.add_subparsers(help='Sub command help', dest='action')

        parser_ls = subparsers.add_parser('ls', help='Lists the Module')
        parser_ls.add_argument("module", nargs='?', help="Package [default = None]", default=None).completer = module_completer

        parser_gen = subparsers.add_parser('generate', help='Generates the Module sources and CMake files')
        parser_gen.add_argument("--link", help="Link instead of copy source files [default = False]", action="store_true", default=False)
        parser_gen.add_argument("module", nargs='?', help="Package [default = None]", default=None).completer = module_completer
        parser_gen.add_argument("destination", nargs='?', help="Path to destination [default = None]", default=None).completer = module_completer

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        retval = 0

        if args.action is None:
            sys.exit(-1)
            
        src = args.module

        if src is not None:
            if src is ".":
                src = None

        if args.no_workspace:
            coreRoot = os.environ.get("NOVA_CORE_ROOT")
            if coreRoot is None:
                CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
                sys.exit(-100)

            if src is not None:
                src = os.path.join(coreRoot, "modules", src)

        if args.action == "ls":
            retval = ls(src, args.no_workspace, args.verbose)

        if args.action == "generate":
            dst = args.destination
            if dst is not None:
                if dst is ".":
                    dst = None

            coreWorkspace = os.environ.get("NOVA_WORKSPACE_ROOT")
            if coreWorkspace is None:
                CoreConsole.out("NOVA_WORKSPACE_ROOT environment variable not found")
                sys.exit(-100)

            if dst is None:
                dst = os.path.join(coreWorkspace, "generated", "modules")

            retval = generate(src, dst, args.no_workspace, args.verbose, args.link)

        if args.action == "clean":
            CoreConsole.out(Fore.LIGHTCYAN_EX + "Todo ;-)" + Fore.RESET)

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1000)
    except Exception as e:
        CoreConsole.out("Exception: " + CoreConsole.error(repr(e)))
        sys.exit(-1000)

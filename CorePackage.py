#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import argparse
import argcomplete
import io

from novalabs.core.CorePackage import *

def action_completer(prefix, parsed_args, **kwargs):
    mm = ["ls", "generate"]
    return (m for m in mm if m.startswith(prefix))


def package_completer(prefix, parsed_args, **kwargs):
    if parsed_args.action is not None:
        coreRoot = os.environ.get("NOVA_CORE_ROOT")
        if coreRoot is not None:
            mm = listDirectories(os.path.join(coreRoot, "packages"))
            return (m for m in mm if m.startswith(prefix))


def ls(srcPath, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    package = CorePackage()
    package.open(srcPath)

    table = [package.getSummary(coreRoot)]
    CoreConsole.out(CoreConsole.h1("PACKAGE"))
    CoreConsole.out(CoreConsole.table(table, package.getSummaryFields()))

    if not package.valid:
        printSuccessOrFailure(False)
        return -1

    # --- List configurations -----------------------------------------------------
    table = []
    tmp = package.listConfigurationFiles()
    for x in tmp:
        configuration = CoreConfiguration()
        configuration.open(x, package)

        table.append(configuration.getSummary(package.packageRoot))

        if not configuration.valid:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("CONFIGURATIONS"))
        CoreConsole.out(CoreConsole.table(table, CoreConfiguration.getSummaryFields()))
    # -----------------------------------------------------------------------------

    # --- List messages -----------------------------------------------------------
    table = []
    tmp = package.listMessageFiles()
    for x in tmp:
        message = CoreMessage()
        message.open(x, package)

        table.append(message.getSummary(package.packageRoot))

        if not message.valid:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MESSAGES"))
        CoreConsole.out(CoreConsole.table(table, CoreMessage.getSummaryFields()))
    # -----------------------------------------------------------------------------

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def generate(srcPath, dstPath, workspaceMode, verbose, link=False, relPathSrc=None, relPathDst=None):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    package = CorePackage()
    package.open(srcPath)

    targetPath = dstPath

    if workspaceMode:
        package.generate(targetPath, "${WORKSPACE_PACKAGES_PATH}", link=link)
    else:
        package.generate(targetPath, link=link)

    table = [package.getSummaryGenerate(relPathSrc, relPathDst)]

    CoreConsole.out(CoreConsole.h1("PACKAGE"))
    CoreConsole.out(CoreConsole.table(table, package.getSummaryFieldsGenerate()))

    if not package.generated:
        printSuccessOrFailure(False)
        return -1

    #TODO move the following inside CorePackage class...

    # --- Generate configurations -------------------------------------------------
    table = []
    tmp = package.listConfigurationFiles()
    for x in tmp:
        conf = CoreConfiguration()
        if conf.open(x, package):
            conf.generate(targetPath)

        table.append(conf.getSummaryGenerate(package.packageRoot, package.destination))

        if not conf.generated:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("CONFIGURATIONS"))
        CoreConsole.out(CoreConsole.table(table, CoreConfiguration.getSummaryFieldsGenerate()))
    # -----------------------------------------------------------------------------

    # --- Generate messages -------------------------------------------------------
    table = []
    tmp = package.listMessageFiles()
    for x in tmp:
        message = CoreMessage()
        if message.open(x, package):
            message.generate(targetPath)

        table.append(message.getSummaryGenerate(package.packageRoot, package.destination))

        if not message.generated:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MESSAGES"))
        CoreConsole.out(CoreConsole.table(table, CoreMessage.getSummaryFieldsGenerate()))
    # -----------------------------------------------------------------------------

    # --- Generate documentatio ---------------------------------------------------
    docs = listFilesByExtension(os.path.join(targetPath, package.name, "doc"), "adoc")
    nodesDocs = listFilesByExtension(os.path.join(targetPath, package.name, "doc", "nodes"), "adoc")
    paramsDocs = listFilesByExtension(os.path.join(targetPath, package.name, "doc", "params"), "adoc")
    msgsDocs = listFilesByExtension(os.path.join(targetPath, package.name, "doc", "msgs"), "adoc")

    print(docs)
    # -----------------------------------------------------------------------------

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


if '__main__' == __name__:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", help="Verbose output [default = False]", action="store_true", default=False)
        parser.add_argument("--no-workspace", help="No Workspace mode", action="store_true", default=False)
        subparsers = parser.add_subparsers(help='Sub command help', dest='action')

        parser_ls = subparsers.add_parser('ls', help='Lists the Module')
        parser_ls.add_argument("package", nargs='?', help="Package [default = None]", default=None).completer = package_completer

        parser_gen = subparsers.add_parser('generate', help='Generates the Module sources and CMake files')
        parser_gen.add_argument("--link", help="Link instead of copy source files [default = False]", action="store_true", default=False)
        parser_gen.add_argument("package", nargs='?', help="Package [default = None]", default=None).completer = package_completer
        parser_gen.add_argument("destination", nargs='?', help="Path to destination [default = None]", default=None)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        retval = 0

        if args.action is None:
            sys.exit(-1)

        src = args.package
        workspaceMode = not args.no_workspace
        verbose = args.verbose

        if not verbose:
            CoreConsole.debug = False
            CoreConsole.verbose = False

        if src is not None:
            if src is ".":
                src = None

        if workspaceMode:
            coreRoot = os.environ.get("NOVA_CORE_ROOT")
            if coreRoot is not None:
                CoreConsole.info(Fore.MAGENTA + "NOVA_CORE_ROOT" + Fore.RESET + ": " + CoreConsole.highlightFilename(coreRoot))
            else:
                CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
                sys.exit(-1)

            if src is not None:
                src = os.path.join(coreRoot, "packages", src)

        if args.action == "ls":
            retval = ls(src, verbose)

        if args.action == "generate":
            dst = args.destination
            if dst is not None:
                if dst is ".":
                    dst = None

            if workspaceMode:
                coreWorkspace = os.environ.get("NOVA_WORKSPACE_ROOT")
                if coreWorkspace is None:
                    CoreConsole.out("NOVA_WORKSPACE_ROOT environment variable not found")
                    sys.exit(-1)

                if dst is None:
                    dst = os.path.join(coreWorkspace, "generated", "packages")

            retval = generate(src, dst, workspaceMode, verbose, args.link)

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1)

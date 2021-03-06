#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import argparse
import argcomplete
import io

from novalabs.core.CorePackage import *
import novalabs.generators as generators

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

    # --- List nodes --------------------------------------------------------------
    table = []
    tmp = package.listNodeFiles()
    for x in tmp:
        node = CoreNode()
        node.open(x, package)

        table.append(node.getSummary(package.packageRoot))

        if not node.valid:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("NODES"))
        CoreConsole.out(CoreConsole.table(table, CoreNode.getSummaryFields()))
    # -----------------------------------------------------------------------------

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def generateDocumentation(name, git_rev, docs,nodes,params,msgs):
    buffer = list()

    buffer.append(":icons: font")
    buffer.append("= [Package] " + name)
    buffer.append("")
    for doc in docs:
        if doc != "index.adoc":
            buffer.append("include::doc/" + doc + "[tabsize=2]")
    buffer.append("")

    if nodes:
        buffer.append("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        buffer.append("")
        buffer.append("== Nodes")
        for node in nodes:
            buffer.append("include::doc/nodes/" + node + "[tabsize=2]")

    if params:
        buffer.append("")
        buffer.append("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        buffer.append("")
        buffer.append("== Parameters")
        for param in params:
            buffer.append("include::doc/params/" + param + "[tabsize=2]")

    if msgs:
        buffer.append("")
        buffer.append("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        buffer.append("")
        buffer.append("== Messages")
        buffer.append("")
        for msg in msgs:
            buffer.append("include::doc/msgs/" + msg + "[tabsize=2]")

    if git_rev is not None:
        buffer.append("")
        buffer.append("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        buffer.append("[appendix]")
        buffer.append("== Source code")
        buffer.append("")
        buffer.append("[NOTE]")
        buffer.append("===============================")
        buffer.append("GIT Description of source code +")
        buffer.append("`" + git_rev + "`")
        buffer.append("===============================")

    return "\n".join(buffer)


def generate(srcPath, dstPath, workspaceMode, verbose, link=False, relPathSrc=None, relPathDst=None):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    package = CorePackage()
    package.open(srcPath)

    targetPath = dstPath

    package_gen = generators.CorePackageGenerator(package)

    if workspaceMode:
        package_gen.generate(targetPath, "${WORKSPACE_PACKAGES_PATH}", link=link)
    else:
        package_gen.generate(targetPath, link=link)

    table = [package_gen.getSummaryGenerate(relPathSrc, relPathDst)]

    CoreConsole.out(CoreConsole.h1("PACKAGE"))
    CoreConsole.out(CoreConsole.table(table, generators.CorePackageGenerator.getSummaryFieldsGenerate()))

    if not package_gen.generated:
        printSuccessOrFailure(False)
        return -1

    #TODO move the following inside CorePackage class...

    # --- Generate configurations -------------------------------------------------
    table = []
    tmp = package.listConfigurationFiles()
    for x in tmp:
        conf = CoreConfiguration()
        gen = generators.CoreConfigurationGenerator(conf)
        if conf.open(x, package):
            gen.generate(targetPath)

        table.append(gen.getSummaryGenerate(package.packageRoot, package_gen.destination))

        if not gen.generated:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("CONFIGURATIONS"))
        CoreConsole.out(CoreConsole.table(table, generators.CoreConfigurationGenerator.getSummaryFieldsGenerate()))
    # -----------------------------------------------------------------------------

    # --- Generate messages -------------------------------------------------------
    table = []
    tmp = package.listMessageFiles()
    for x in tmp:
        message = CoreMessage()
        gen = generators.CoreMessageGenerator(message)

        if message.open(x, package):
            gen.generate(targetPath)

        table.append(gen.getSummaryGenerate(package.packageRoot, package_gen.destination))

        if not gen.generated:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MESSAGES"))
        CoreConsole.out(CoreConsole.table(table, generators.CoreMessageGenerator.getSummaryFieldsGenerate()))
    # -----------------------------------------------------------------------------

    # --- Generate nodes ----------------------------------------------------------
    table = []
    tmp = package.listNodeFiles()
    for x in tmp:
        node = CoreNode()
        gen = generators.CoreNodeGenerator(node)
        if node.open(x, package):
            gen.generate(targetPath)

        table.append(gen.getSummaryGenerate(package.packageRoot, package_gen.destination))

        if not gen.generated:
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MESSAGES"))
        CoreConsole.out(CoreConsole.table(table,  generators.CoreNodeGenerator.getSummaryFieldsGenerate()))
    # -----------------------------------------------------------------------------

    # --- Generate documentation --------------------------------------------------
    #TODO: This is just a proof of concept - I must rewrite it as it should be written

    docs = listFilesByExtension(os.path.join(targetPath, package.name, "doc"), "adoc")
    paramsDocs = listFilesByExtension(os.path.join(targetPath, package.name, "doc", "params"), "adoc")
    msgsDocs = listFilesByExtension(os.path.join(targetPath, package.name, "doc", "msgs"), "adoc")
    nodesDocs = listFilesByExtension(os.path.join(targetPath, package.name, "doc", "nodes"), "adoc")

    index = generateDocumentation(package.name, package.git_rev, docs, nodesDocs, paramsDocs, msgsDocs)

    docDestination = os.path.join(targetPath, package.name, "index.adoc")

    try:
        try:
            sink = open(docDestination, 'w')
            sink.write(index)
        except IOError as e:
            raise CoreError(str(e.strerror), e.filename)
    except CoreError as e:
        isOk = False
        CoreConsole.fail("Cannot generate documentation: " + str(e))
        CoreConsole.out(CoreConsole.error("Cannot generate documentation: " + str(e)))
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

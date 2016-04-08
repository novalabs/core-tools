#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argcomplete
import argparse

from CoreUtils import *
from CoreMessage import *
from CoreConfiguration import *
from CoreNode import *

import shutil


class CorePackage:
    schema = '{ "type": "record", "name": "CorePackage", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" } ] }'

    def __init__(self):
        self.data = []
        self.filename = ""
        self.root = None
        self.packageRoot = ""
        self.source = ""
        self.name = ""
        self.description = ""
        self.destination = None
        self.valid = False
        self.reason = ""
        self.buffer = []
        self.sources = []
        self.includes = []
        self.cmake = ""
        self.cmakePathPrefix = None
        self.generated = False

    def openJSON(self, jsonFile):
        CoreConsole.info("CORE_PACKAGE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CorePackage.schema)

            if self.filename == self.data["name"]:
                self.source = jsonFile
                self.name = self.data["name"]
                self.description = self.data["description"]

                self.valid = True

                return True
            else:
                  raise CoreError("Package filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::openJSON: " + self.reason)
            self.valid = False
            return False

    def open(self, root=None, name=None):
        self.valid = False

        if root is not None:
            if name is not None:
                self.packageRoot = os.path.join(root, name)
            else:
                self.packageRoot = root
        else:
            self.packageRoot = self.getRoot()

        if self.packageRoot is not None:
            (root, name) = os.path.split(self.packageRoot)
        else:
            return False

        self.root = root
        self.filename = name

        jsonFile = os.path.join(self.packageRoot, "CORE_PACKAGE.json")

        try:
            return self.openJSON(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::open: " + self.reason)
            return False

    def getRoot(self):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("CORE_PACKAGE.json")
            if self.root is not None:
                CoreConsole.ok("CorePackage::getRoot: Package found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "CorePackage::getRoot: Not inside a Package"
                CoreConsole.fail(self.reason)

        return self.root

    def generate(self, path, cmakePathPrefix=None):
        self.cmakePathPrefix = cmakePathPrefix
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    path = os.path.join(path, self.name)

                    self.destination = path

                    if not os.path.isdir(self.destination):
                            os.makedirs(self.destination)

                    self.process()

                    CoreConsole.ok("CorePackage::generate " + CoreConsole.highlightFilename(self.destination))

                    self.generated = True

                    return True
                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::generate: " + self.reason)
            return False

    def process(self):
        srcIncludes = os.path.join(self.packageRoot, "include")
        dstIncludes = os.path.join(self.destination, "include", self.name)

        self.includes = listFiles(srcIncludes)
        if len(self.includes) > 0:
            if not os.path.isdir(dstIncludes):
                os.makedirs(dstIncludes)
            for file in self.includes:
                copyOrLink(os.path.join(srcIncludes, file), os.path.join(dstIncludes, file))

        srcSources = os.path.join(self.packageRoot, "src")
        dstSources = os.path.join(self.destination, "src")

        self.sources = listFiles(srcSources)
        if len(self.sources) > 0:
            if not os.path.isdir(dstSources):
                os.makedirs(dstSources)
            for file in self.sources:
                copyOrLink(os.path.join(srcSources, file), os.path.join(dstSources, file))

        self.processCMake()

        self.cmake = os.path.join(self.destination, self.name + "Config.cmake")
        sink = open(self.cmake, 'w')

        sink.write("\n".join(self.buffer))

    def processCMake(self):
        self.buffer = []

        if self.cmakePathPrefix is None:
            self.buffer.append('LIST( APPEND WORKSPACE_PACKAGES_MODULES ' + self.name + ' )')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_SOURCES')
            for src in self.sources:
                self.buffer.append('  ' + os.path.join(self.destination, "src", src))
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_INCLUDES')
            self.buffer.append('  ' + os.path.join(self.destination, "include"))
            self.buffer.append(')')
            self.buffer.append('')
        else:
            self.buffer.append('LIST( APPEND WORKSPACE_PACKAGES_MODULES ' + self.name + ' )')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_SOURCES')
            for src in self.sources:
                self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/src/" + src)
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_INCLUDES')
            self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/include")
            self.buffer.append(')')
            self.buffer.append('')

    def getSummary(self, relpath=None):
        table = []
        if self.valid:
            if relpath is not None:
                return [CoreConsole.highlight(self.name), self.description, os.path.relpath(self.packageRoot, relpath)]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.packageRoot]
        else:
            return ["", CoreConsole.error(self.reason), ""]

    @staticmethod
    def getSummaryFields(self=None):
        return ["Name", "Description", "Root"]

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        table = []
        if self.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.packageRoot, relpathSrc)
            else:
                src = self.packageRoot

            if relpathDst is not None:
                dst = os.path.relpath(self.destination, relpathDst)
            else:
                dst = self.destination

            if self.generated:
                return [CoreConsole.highlight(self.name), self.description, src, dst]
            else:
                return [CoreConsole.highlight(self.name), self.description, src, CoreConsole.error(self.reason)]
        else:
            return ["", CoreConsole.error(self.reason), ""]

    @staticmethod
    def getSummaryFieldsGenerate(self=None):
        return ["Name", "Description", "Root", "Generate"]

    def listMessageFiles(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "messages")
        return listFilesByAndStripExtension(path, ".json")

    def listConfigurationFiles(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "configurations")
        return listFilesByAndStripExtension(path, ".json")

    def listNodeFiles(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "nodes")
        return listFilesByAndStripExtension(path, ".json")

    def getMessageFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "messages", (x + ".json"))
        if os.path.isfile(path):
            return path
        else:
            raise CoreError("Message " + x + " not found in package")

    def getConfigurationFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "configurations", (x + ".json"))
        if os.path.isfile(path):
            return path
        else:
            raise CoreError("Configuration " + x + " not found in package")

    def getNodeFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "nodes", (x + ".json"))
        if os.path.isfile(path):
            return path
        else:
            raise CoreError("Node " + x + " not found in package")

    def getIncludeDir(self, namespace=""):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        if namespace == "":
            namespace = self.name
        return os.path.join(self.packageRoot, "include", namespace)

    @staticmethod
    def check(root, name=None):
        if name is None:
            return os.path.exists(os.path.join(root, "CORE_PACKAGE.json"))
        else:
            return os.path.exists(os.path.join(root, name, "CORE_PACKAGE.json"))


def action_completer(prefix, parsed_args, **kwargs):
    mm = ["ls", "generate", "clean"]
    return (m for m in mm if m.startswith(prefix))


def package_completer(prefix, parsed_args, **kwargs):
    if parsed_args.action is not None:
        coreRoot = os.environ.get("NOVA_CORE_ROOT")
        if coreRoot is not None:
            mm = listDirectories(os.path.join(coreRoot, "packages"))  # TODO ...
            return (m for m in mm if m.startswith(prefix))


def ls(srcPath, workspaceMode, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    p = CorePackage()
    p.open(srcPath)

    table = [p.getSummary(coreRoot)]
    CoreConsole.out(CoreConsole.h1("PACKAGE"))
    CoreConsole.out(CoreConsole.table(table, p.getSummaryFields()))

    if not p.valid:
        return -101

    isOk = True

    table = []
    tmp = p.listNodeFiles()
    for x in tmp:
        n = CoreNode()
        n.open(p, x)
        table.append([CoreConsole.highlight(n.namespace), CoreConsole.highlight(n.name), n.description, os.path.relpath(n.source, p.packageRoot)])
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("NODES"))
        CoreConsole.out(CoreConsole.table(table, ["NS", "Name", "Description", "Source"]))

    table = []
    tmp = p.listConfigurationFiles()
    for x in tmp:
        m = CoreConfiguration()
        if m.open(x, p):
            table.append([CoreConsole.highlight(m.namespace), CoreConsole.highlight(m.name), m.description, os.path.relpath(m.source, p.packageRoot)])
        else:
            table.append(["", "", "", CoreConsole.error(m.reason), ""])
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("CONFIGURATIONS"))
        CoreConsole.out(CoreConsole.table(table, ["NS", "Name", "Description", "Source"]))

    table = []
    tmp = p.listMessageFiles()
    for x in tmp:
        m = CoreMessage()
        if m.open(x, p):
            table.append([CoreConsole.highlight(m.namespace), CoreConsole.highlight(m.name), m.description, os.path.relpath(m.source, p.packageRoot)])
        else:
            table.append(["", "", "", CoreConsole.error(m.reason), ""])
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MESSAGES"))
        CoreConsole.out(CoreConsole.table(table, ["NS", "Name", "Description", "Source"]))

    if isOk:
        return 0
    else:
        return -2


def generate(srcPath, dstPath, workspaceMode, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    p = CorePackage()
    p.open(srcPath)

    if not p.valid:
        return -101

    isOk = True

    targetPath = dstPath

    if workspaceMode:
        isOk = p.generate(targetPath, "${WORKSPACE_PACKAGES_PATH}")
    else:
        isOk = p.generate(targetPath)

    table = [p.getSummaryGenerate()]

    CoreConsole.out(CoreConsole.h1("PACKAGE"))
    CoreConsole.out(CoreConsole.table(table, p.getSummaryFieldsGenerate()))

    table = []
    tmp = p.listNodeFiles()
    for x in tmp:
        n = CoreNode()
        n.open(p, x)
        table.append([CoreConsole.highlight(n.namespace), CoreConsole.highlight(n.name), n.description, os.path.relpath(n.source, p.packageRoot)])
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("NODES"))
        CoreConsole.out(CoreConsole.table(table, ["NS", "Name", "Description", "Source"]))

    table = []
    tmp = p.listConfigurationFiles()
    for x in tmp:
        m = CoreConfiguration()
        if m.open(x, p):
            if m.generate(targetPath):
                table.append([CoreConsole.highlight(m.namespace), CoreConsole.highlight(m.name), m.description, os.path.relpath(m.source, p.packageRoot),
                              os.path.relpath(m.destination, p.destination)])
            else:
                table.append(
                    [CoreConsole.highlight(m.namespace), CoreConsole.highlight(m.name), m.description, os.path.relpath(m.source, p.packageRoot), CoreConsole.error(m.reason)])
                isOk = False
        else:
            table.append(["", "", "", CoreConsole.error(m.reason), ""])
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("CONFIGURATIONS"))
        CoreConsole.out(CoreConsole.table(table, ["NS", "Name", "Description", "Source", "Destination"]))

    table = []
    tmp = p.listMessageFiles()
    for x in tmp:
        m = CoreMessage()
        if m.open(x, p):
            if m.generate(targetPath):
                table.append([CoreConsole.highlight(m.namespace), CoreConsole.highlight(m.name), m.description, os.path.relpath(m.source, p.packageRoot),
                              os.path.relpath(m.destination, p.destination)])
            else:
                table.append(
                    [CoreConsole.highlight(m.namespace), CoreConsole.highlight(m.name), m.description, os.path.relpath(m.source, p.packageRoot), CoreConsole.error(m.reason)])
                isOk = False
        else:
            table.append(["", "", "", CoreConsole.error(m.reason), ""])
            isOk = False
    if len(tmp) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MESSAGES"))
        CoreConsole.out(CoreConsole.table(table, ["NS", "Name", "Description", "Source", "Destination"]))

    if isOk:
        return 0
    else:
        return -2


if '__main__' == __name__:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", help="Verbose output [default = False]", action="store_true", default=False)
        parser.add_argument("--no-workspace", help="No Workspace mode", action="store_false", default=True)
        subparsers = parser.add_subparsers(help='Sub command help', dest='action')

        parser_ls = subparsers.add_parser('ls', help='Lists the Module')
        parser_ls.add_argument("package", nargs='?', help="Package [default = None]", default=None).completer = package_completer

        parser_gen = subparsers.add_parser('generate', help='Generates the Module sources and CMake files')
        parser_gen.add_argument("package", nargs='?', help="Package [default = None]", default=None).completer = package_completer
        parser_gen.add_argument("destination", nargs='?', help="Path to destination [default = None]", default=None)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        if not args.verbose:
            CoreConsole.debug = False
            CoreConsole.verbose = False

        retval = 0

        src = args.package

        if src is not None:
            if src is ".":
                src = None

        if args.no_workspace:
            coreRoot = os.environ.get("NOVA_CORE_ROOT")
            if coreRoot is not None:
                CoreConsole.info(Fore.MAGENTA + "NOVA_CORE_ROOT" + Fore.RESET + ": " + CoreConsole.highlightFilename(coreRoot))
            else:
                CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
                sys.exit(-100)

            if src is not None:
                src = os.path.join(coreRoot, "packages", src)

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
                dst = os.path.join(coreWorkspace, "generated", "packages")

            retval = generate(src, dst, args.no_workspace, args.verbose)

        if args.action == "clean":
            CoreConsole.out(Fore.LIGHTCYAN_EX + "Todo ;-)" + Fore.RESET)

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1000)
    except Exception as e:
        CoreConsole.out("Exception: " + CoreConsole.error(repr(e)))
        sys.exit(-1000)

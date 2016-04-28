#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

from CoreContainer import *


class Core(CoreContainer):
    schema = '{ "type": "record", "name": "Core", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" } ] }'

    def __init__(self):
        CoreContainer.__init__(self)

        self.filename = ""
        self.coreRoot = None
        self.source = ""

        self.data = None

        self.name = ""
        self.description = ""

        self.destination = ""

        self.valid = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("CORE_PACKAGE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, Core.schema)
            self.source = jsonFile
            self.name = self.data["name"]
            self.description = self.data["description"]

            self.valid = True

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("Core::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def getRoot(self):
        if self.coreRoot is None:  # Check for cached value
            self.coreRoot = findFileGoingUp("CORE.json")
            if self.coreRoot is not None:
                CoreConsole.ok("Core::getRoot: Core found in " + CoreConsole.highlightFilename(self.coreRoot))
            else:
                self.reason = "Core::getRoot: Not inside a Core"
                CoreConsole.fail(self.reason)

        return self.coreRoot

    def open(self, root=None):
        self.valid = False

        try:
            if root is not None:
                self.coreRoot = root
            else:
                self.coreRoot = self.getRoot()

            if self.coreRoot is None:
                return False

            jsonFile = os.path.join(self.coreRoot, "CORE.json")

            self.openPackages()
            self.openModules()

            return self.openJSON(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("Core::open: " + self.reason)
            return False

    def getPackagesRoot(self):
        return os.path.join(self.getRoot(), "packages")

    def getModulesRoot(self):
        return os.path.join(self.getRoot(), "modules")


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
        table.append([CoreConsole.highlight(core.name), core.description, core.coreRoot])
        CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "Root"]))
    else:
        CoreConsole.out(CoreConsole.error(core.reason))

    if not core.valid:
        return -1

    isOk = True

    table = []
    core.openPackages()

    for package in core.validPackages:
        table.append(package.getSummary(core.coreRoot))

    for package in core.invalidPackages:
        table.append(package.getSummary(core.coreRoot))
        isOk = False

    if (len(core.validPackages) + len(core.invalidPackages)) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGES"))
        CoreConsole.out(CoreConsole.table(table, CorePackage.getSummaryFields()))

    table = []
    core.openModules()

    for module in core.validModules:
        table.append(module.getSummary(core.coreRoot))

    for module in core.invalidModules:
        table.append(module.getSummary(core.coreRoot))
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


if '__main__' == __name__:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", help="Verbose output [default = False]", action="store_true", default=False)
        subparsers = parser.add_subparsers(help='Sub command help', dest='action')

        parser_ls = subparsers.add_parser('ls', help='Lists the Module')
        parser_ls.add_argument("path", nargs='?', help="Path to Core [default = None]", default=None)

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

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1)

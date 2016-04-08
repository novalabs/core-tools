#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argcomplete
import argparse

from CoreUtils import *
from CorePackage import *
from CoreModule import *
from CoreContainer import *
import git, os, shutil

class Core(CoreContainer):
    schema = '{ "type": "record", "name": "Core", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" } ] }'

    def __init__(self):
        CoreContainer.__init__(self)

        self.data = []
        self.filename = ""
        self.coreRoot = ""
        self.source = ""
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

            return True
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("Core::openJSON: " + self.reason)
            self.valid = False

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



def init(url, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    DIR_NAME = "CoreRepos"
    REMOTE_URL = "https://github.com/novalabs/core-repos.git"

    if os.path.isdir(DIR_NAME):
        pass
        shutil.rmtree(DIR_NAME)

    os.mkdir(DIR_NAME)

    repo = git.Repo.init(DIR_NAME)
    origin = repo.create_remote('origin', REMOTE_URL)
    origin.fetch()
    origin.pull(origin.refs[0].remote_head)

    print "---- DONE ----"

def ls(srcPath, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    core = Core()
    core.open(srcPath)

    table = []
    if core.valid:
        table.append([CoreConsole.highlight(core.name), core.description, core.coreRoot])
    else:
        table.append(["", "", "", CoreConsole.error(core.reason)])

    CoreConsole.out(CoreConsole.h1("CORE"))
    CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "Root"]))

    if not core.valid:
        return -101

    isOk = True

    table = []
    core.openPackages()

    for x in core.validPackages:
        table.append(x.getSummary(core.coreRoot))

    for x in core.invalidPackages:
        table.append(x.getSummary(core.coreRoot))

    if (len(core.validPackages) + len(core.invalidPackages)) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGES"))
        CoreConsole.out(CoreConsole.table(table, CorePackage.getSummaryFields()))

    table = []
    tmp = core.openModules()

    for x in core.validModules:
        table.append([CoreConsole.highlight(x.name), x.description, os.path.relpath(x.source, core.coreRoot)])

    for x in core.invalidModules:
        table.append(["", CoreConsole.error(x.reason), ""])

    if (len(core.validModules) + len(core.invalidModules)) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MODULES"))
        CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "Source"]))

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

        parser_init = subparsers.add_parser('init', help='Initializes a Core environment in current directory')
        parser_init.add_argument("url", nargs='?', help="url to fetch definitions from [default = None]", default=None)

        parser_ls = subparsers.add_parser('ls', help='Lists the Module')
        parser_ls.add_argument("package", nargs='?', help="Package [default = None]", default=None).completer = package_completer

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        retval = 0

        if args.action == "ls":
            src = args.package

            if src is not None:
                if src is ".":
                    src = None

            if args.no_workspace:
                if src is None:
                    coreRoot = os.environ.get("NOVA_CORE_ROOT")
                    if coreRoot is None:
                        CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
                        sys.exit(-100)

                    src = coreRoot

            retval = ls(src, args.verbose)

        if args.action == "init":
            url = args.url

            retval = init(url, args.verbose)

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1000)
    except Exception as e:
        CoreConsole.out("Exception: " + CoreConsole.error(repr(e)))
        sys.exit(-1000)

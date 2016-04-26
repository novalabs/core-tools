#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argcomplete, argparse

from CoreContainer import *
from CoreUtils import *
from ModuleTarget import *
from CoreModule import generate as generateModule
from CorePackage import generate as generatePackage
import subprocess
from Core import *

class CoreWorkspace(CoreContainer):
    def __init__(self):
        CoreContainer.__init__(self)

        self.root = None
        self.sources = None
        self.generated = None
        self.build = None
        self.valid = False
        self.opened = False
        self.reason = ""
        self.requiredModules = []
        self.requiredPackages = []
        self.core = Core()
        self.packagesCoreDependencies = []
        self.packagesWorkspaceDependencies = []
        self.packagesNoneDependencies = []
        self.modulesWorkspaceDependencies = []
        self.modulesCoreDependencies = []
        self.modulesNoneDependencies = []

    def getRoot(self, cwd = None):
        if self.root is None: # Check for cached value
            self.root = findFileGoingUp("WORKSPACE.json", cwd)
            if self.root is not None:
                CoreConsole.ok("CoreWorkspace::getRoot: Workspace found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "CoreWorkspace::getRoot: Not inside a Workspace"
                CoreConsole.fail(self.reason)

        return self.root

    def clean(self, force):
        root = self.getRoot()
        if root is not None:
            if not force:
                print("OK: " + root)
        else:
            print("!!!!")

    def getSourcesPath(self):
        if self.sources is None: # Check for cached value
            if self.getRoot() is not None:
                tmp = os.path.join(self.root, "sources")
                if os.path.isdir(tmp):
                    self.sources = tmp
                else:
                    self.reason = "CoreWorkspace::getSourcesPath: 'sources' directory not found inside Workspace"
                    CoreConsole.fail(self.reason)
                    self.sources = None
            else:
                self.sources = None

        return self.sources

    def getGeneratedPath(self):
        try:
            if self.generated is None: # Check for cached value
                if self.getRoot() is not None:
                    tmp = os.path.join(self.root, "generated")
                    if not os.path.isdir(tmp):
                        try:
                            os.makedirs(tmp)
                        except OSError as e:
                            raise CoreError("I/0 Error: " + str(e.strerror), e.filename)
                    self.generated = tmp
                else:
                    self.generated = None
        except CoreError as e:
            self.reason = str(e.value)
            CoreConsole.fail("CoreWorkspace::getGeneratedPath: " + self.reason)

        return self.generated

    def getBuildPath(self):
        try:
            if self.build is None: # Check for cached value
                if self.getRoot() is not None:
                    tmp = os.path.join(self.root, "build")
                    if not os.path.isdir(tmp):
                        try:
                            os.makedirs(tmp)
                        except OSError as e:
                            raise CoreError("I/0 Error: " + str(e.strerror), e.filename)
                    self.build = tmp
                else:
                    self.build = None
        except CoreError as e:
            self.reason = str(e.value)
            CoreConsole.fail("CoreWorkspace::getBuildPath: " + self.reason)

        return self.build

    def getPackagesRoot(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        return os.path.join(self.getSourcesPath(), "packages")

    def getModulesRoot(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        return self.getSourcesPath()

    def getModuleTargetsRoot(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        return os.path.join(self.getSourcesPath(), "targets")

    def open(self, root = None, coreRoot = None): # If root is None it will use CWD
        self.root = root

        if self.getRoot() is None:
            self.reason = "CoreWorkspace::open: Not a valid Workspace [" + self.reason + "]"
            return False

        if self.getSourcesPath() is None:
            self.reason = "CoreWorkspace::open: Not a valid Workspace [" + self.reason + "]"
            return False

        if self.getGeneratedPath() is None:
            self.reason = "CoreWorkspace::open: Not a valid Workspace [" + self.reason + "]"
            return False

        if self.getBuildPath() is None:
            self.reason = "CoreWorkspace::open: Not a valid Workspace [" + self.reason + "]"
            return False

        self.valid = True
        self.opened = True

        self.openModules()
        self.openPackages()
        self.openModuleTargets()

        self.opened = self.core.open(coreRoot)

        return self.opened

    def getRequiredModules(self):
        tmp = []
        for x in self.validModuleTargets:
            tmp.append(x.module)

        self.requiredModules = list(set(tmp))

        return  self.requiredModules

    def getRequiredPackages(self):
        tmp = []
        for x in self.validModuleTargets:
            for y in x.requiredPackages:
                tmp.append(y)

            m = self.core.getModuleByName(x.module)
            for y in m.requiredPackages:
                tmp.append(y)

        self.requiredPackages = list(set(tmp))
        self.requiredPackages.sort()

        return self.requiredPackages

    def checkPackagesDependencies(self):
        self.packagesWorkspaceDependencies = []
        self.packagesCoreDependencies = []
        self.packagesNoneDependencies = []
        isOk = True

        for x in self.getRequiredPackages():
            tmpW = self.getPackageByName(x)
            tmpC = self.core.getPackageByName(x)

            if tmpW is not None:
                self.packagesWorkspaceDependencies.append(tmpW)
            else:
                if tmpC is not None:
                    self.packagesCoreDependencies.append(tmpC)
                else:
                    self.packagesNoneDependencies.append(x)
                    isOk = False

        return isOk

    def getPackagesDependenciesSummary(self):
        table = []

        for x in self.getRequiredPackages():
            tmpW = self.getPackageByName(x)
            tmpC = self.core.getPackageByName(x)

            l = CoreConsole.highlight(x)
            s = ""
            n = ""
            if tmpW is not None:
                if tmpC is None:
                    s = "Workspace"
                else:
                    s = "Workspace"
                    n = "Shadows Core"
            else:
                if tmpC is not None:
                    s = "Core"
                else:
                    n = CoreConsole.error("Not found")
                    isOk = False

            table.append([l, s, n])

        return table

    @staticmethod
    def getPackagesDependenciesSummaryFields():
        return ["Package", "Source", "Notes"]

    def checkModulesDependencies(self):
        self.modulesWorkspaceDependencies = []
        self.modulesCoreDependencies = []
        self.modulesNoneDependencies = []
        isOk = True

        for x in self.getRequiredModules():
            tmpW = self.getModuleByName(x)
            tmpC = self.core.getModuleByName(x)

            if tmpW is not None:
                self.modulesWorkspaceDependencies.append(tmpW)
            else:
                if tmpC is not None:
                    self.modulesCoreDependencies.append(tmpC)
                else:
                    self.modulesNoneDependencies.append(x)
                    isOk = False

        return isOk

    def getModulesDependenciesSummary(self):
        table = []

        for x in self.getRequiredModules():
            tmpW = self.getModuleByName(x)
            tmpC = self.core.getModuleByName(x)

            l = CoreConsole.highlight(x)
            s = ""
            n = ""
            if tmpW is not None:
                if tmpC is None:
                    s = "Workspace"
                else:
                    s = "Workspace"
                    n = "Shadows Core"
            else:
                if tmpC is not None:
                    s = "Core"
                else:
                    n = CoreConsole.error("Not found")
                    isOk = False

            table.append([l, s, n])

        return table

    @staticmethod
    def getModulesDependenciesSummaryFields():
        return ["Module", "Source", "Notes"]

# ENVIRONMENT VARIABLES -------------------------------------------------------

NOVA_CORE_ROOT = os.environ.get("NOVA_CORE_ROOT")
if NOVA_CORE_ROOT is None:
    CoreConsole.out(CoreConsole.error("NOVA_CORE_ROOT environment variable not found"))
    sys.exit(-1)

NOVA_CORE_TOOLCHAIN = os.environ.get("NOVA_CORE_TOOLCHAIN")
if NOVA_CORE_TOOLCHAIN is None:
    CoreConsole.out(CoreConsole.error("NOVA_CORE_TOOLCHAIN environment variable not found"))
    sys.exit(-1)

NOVA_CHIBIOS_ROOT = os.environ.get("NOVA_CHIBIOS_ROOT")
if NOVA_CHIBIOS_ROOT is None:
    CoreConsole.out(CoreConsole.error("NOVA_CHIBIOS_ROOT environment variable not found"))
    sys.exit(-1)

NOVA_WORKSPACE_ROOT = os.environ.get("NOVA_WORKSPACE_ROOT")
# check later if None - do not interfere with initialize

CMAKE_PREFIX_PATH = os.environ.get("CMAKE_PREFIX_PATH")
if CMAKE_PREFIX_PATH is None:
    CoreConsole.out(CoreConsole.error("CMAKE_PREFIX_PATH environment variable not found"))
    sys.exit(-1)

CMAKE_MODULE_PATH = os.environ.get("CMAKE_MODULE_PATH")
if CMAKE_MODULE_PATH is None:
    CoreConsole.out(CoreConsole.error("CMAKE_MODULE_PATH environment variable not found"))
    sys.exit(-1)

def cmakeCommand(chip, source):
    cmake_cmd = "cmake --verbose"
    cmake_cmd += " -DSTM32_CHIP=" + chip
    cmake_cmd += " -DCMAKE_TOOLCHAIN_FILE=" + CMAKE_PREFIX_PATH + "/gcc_stm32.cmake"
    cmake_cmd += " -DCMAKE_BUILD_TYPE=Debug"
    cmake_cmd += " -DTOOLCHAIN_PREFIX=" + NOVA_CORE_TOOLCHAIN
    cmake_cmd += " -DCMAKE_MODULE_PATH=" + CMAKE_MODULE_PATH
    cmake_cmd += " -DCHIBIOS_ROOT="+NOVA_CHIBIOS_ROOT
    cmake_cmd += " -DNOVA_ROOT="+NOVA_CORE_ROOT
    cmake_cmd += " -DNOVA_WORKSPACE_ROOT="+NOVA_WORKSPACE_ROOT
    cmake_cmd += ' -G "Eclipse CDT4 - Unix Makefiles"'
    cmake_cmd += " " + source

    return cmake_cmd

def createJSON(root):
    buffer = []

    buffer.append('{')
    buffer.append('  "name": "Workspace",')
    buffer.append('  "description": "Workspace",')
    buffer.append('}')
    buffer.append('')

    sink = open(os.path.join(root, "WORKSPACE.json"), 'w')

    sink.write("\n".join(buffer))

def createSetup(root):
    buffer = []

    buffer.append('source ' + os.path.join(NOVA_CORE_ROOT, "setup.sh"))
    buffer.append('export NOVA_WORKSPACE_ROOT=' + root)
    buffer.append('')

    sink = open(os.path.join(root, "setup.sh"), 'w')

    sink.write("\n".join(buffer))

def action_completer(prefix, parsed_args, **kwargs):
    mm = ["ls", "generate", "init"]
    return (m for m in mm if m.startswith(prefix))

if '__main__' == __name__:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--verbose", help="Verbose output [default = False]", action="store_true", default=False)
        subparsers = parser.add_subparsers(help='Sub command help', dest='action')

        parser_ls = subparsers.add_parser('ls', help='Lists the Module')

        parser_gen = subparsers.add_parser('generate', help='Generates the Workspace sources and CMake files')
        parser_gen.add_argument("--force", help="Generate even in presence on unmet dependencies [default = False]", action="store_true", default=False)

        parser_init = subparsers.add_parser('initialize', help='Initializes a Workspace')
        parser_init.add_argument("--force", help="Re-Initialize [default = False]", action="store_true", default=False)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        if not args.verbose:
            CoreConsole.debug = False
            CoreConsole.verbose = False


        if args.action == "initialize":
            workspace = CoreWorkspace()

            root = os.getcwd()

            if workspace.getRoot(root) is not None:
                if not args.force:
                    raise CoreError("Workspace already initialized")
                else:
                    CoreConsole.out(CoreConsole.warning("Workspace already initialized, ignoring..."))
                    root = workspace.getRoot()
                    os.unlink(os.path.join(root, "WORKSPACE.json"))
                    tmp = os.path.join(root, "setup.sh")
                    if os.path.isfile(tmp):
                        os.unlink(tmp)

            # create WORKSPACE.json
            createJSON(root)

            # create setup.sh
            createSetup(root)

            # create directories
            mkdir(os.path.join(root, "sources"))
            mkdir(os.path.join(root, "generated"))
            mkdir(os.path.join(root, "build"))

            CoreConsole.out("Workspace initialized.")
            CoreConsole.out("You can now do a 'source setup.sh'")

            sys.exit(0)

        if args.action == "ls":
            workspace = CoreWorkspace()
            workspace.open(coreRoot=NOVA_CORE_ROOT)

            if workspace.opened:
                table = []

                for m in workspace.validModuleTargets:
                    table.append([CoreConsole.highlight(m.name), m.description, m.module])

                for m in workspace.invalidModuleTargets:
                    table.append([CoreConsole.error(m.filename), CoreConsole.error(m.reason), ""])

                if len(table) > 0:
                    CoreConsole.out(CoreConsole.h2("TARGETS"))
                    CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "CoreModule"]))

                table = []

                for p in workspace.validPackages:
                    table.append(p.getSummary(workspace.getRoot()))

                for p in workspace.invalidPackages:
                    table.append(p.getSummary(workspace.getRoot()))

                if len(table) > 0:
                    CoreConsole.out("")
                    CoreConsole.out(CoreConsole.h2("PACKAGES"))
                    CoreConsole.out(CoreConsole.table(table, CorePackage.getSummaryFields()))
            else:
                CoreConsole.out(CoreConsole.error(workspace.reason))

            CoreConsole.out("")
            CoreConsole.out(CoreConsole.h2("PACKAGE DEPENDENCIES"))
            CoreConsole.out(CoreConsole.table(workspace.getPackagesDependenciesSummary(), CoreWorkspace.getPackagesDependenciesSummaryFields()))

            CoreConsole.out("")
            CoreConsole.out(CoreConsole.h2("MODULE DEPENDENCIES"))
            CoreConsole.out(CoreConsole.table(workspace.getModulesDependenciesSummary(), CoreWorkspace.getModulesDependenciesSummaryFields()))

        if args.action == "generate":
            if NOVA_CHIBIOS_ROOT is None:
                CoreConsole.out(CoreConsole.error("NOVA_WORKSPACE_ROOT environment variable not found"))
                sys.exit(-1)

            workspace = CoreWorkspace()
            workspace.open(coreRoot=NOVA_CORE_ROOT)

            if workspace.opened:
                table = []

                isOk = True

                if not workspace.checkPackagesDependencies():
                    if not args.force:
                        raise CoreError("There are unmet Package dependencies: " + ", ".join(workspace.packagesNoneDependencies))

                if not workspace.checkModulesDependencies():
                    if not args.force:
                        raise CoreError("There are unmet Module dependencies: " + ", ".join(workspace.modulesNoneDependencies))

                for x in workspace.packagesCoreDependencies:
                    CoreConsole.out(Fore.MAGENTA + "Generating Core Package dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
                    res = generatePackage(os.path.join(workspace.core.getPackagesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "packages"), True, args.verbose)
                    if res != 0:
                        isOk = False
                    CoreConsole.out('')

                for x in workspace.packagesWorkspaceDependencies:
                    CoreConsole.out(Fore.MAGENTA + "Generating Workspace Package dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
                    res = generatePackage(os.path.join(workspace.getPackagesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "packages"), True, args.verbose)
                    if res != 0:
                        isOk = False
                    CoreConsole.out('')

                for x in workspace.packagesNoneDependencies:
                    CoreConsole.out(Fore.MAGENTA + "Generating Package dependency: " + Style.BRIGHT + x + Style.RESET_ALL)
                    CoreConsole.out(CoreConsole.error("404 not found"))
                    CoreConsole.out('')

                for x in workspace.modulesCoreDependencies:
                    CoreConsole.out(Fore.MAGENTA + "Generating Core Module dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
                    res = generateModule(os.path.join(workspace.core.getModulesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "modules"), True, args.verbose)
                    if res != 0:
                        isOk = False
                    CoreConsole.out('')

                for x in workspace.modulesWorkspaceDependencies:
                    CoreConsole.out(Fore.MAGENTA + "Generating Workspace Module dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
                    res = generateModule(os.path.join(workspace.getModulesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "modules"), True, args.verbose)
                    if res != 0:
                        isOk = False
                    CoreConsole.out('')

                for x in workspace.modulesNoneDependencies:
                    CoreConsole.out(Fore.MAGENTA + "Generating Module dependency: " + Style.BRIGHT + x + Style.RESET_ALL)
                    CoreConsole.out(CoreConsole.error("404 not found"))
                    CoreConsole.out('')

                for m in workspace.validModuleTargets:
                    t = os.path.join(workspace.getSourcesPath(), "targets", m.name)

                    mustGenerate = True
                    exists = False
                    grepped = False

                    if os.path.isdir(t):
                        t2 = os.path.join(t, "CMakeLists.txt")
                        if os.path.isfile(t2):
                            exists = True
                            for line in open(t2):
                                if line.startswith("## TARGET MODULE"): # Grep marker in file
                                    grepped = True
                                    break

                    if exists and not grepped:
                        mustGenerate = False

                    cm = workspace.core.getModuleByName(m.module)
                    if cm is None:
                        cm = workspace.getModuleByName(m.module)

                    # ECLIPSE WORKAROUND BEGIN
                    if not os.path.isdir(os.path.join(t, "modules")):
                        os.mkdir(os.path.join(t, "modules"))

                    if not os.path.isdir(os.path.join(t, "packages")):
                        os.mkdir(os.path.join(t, "packages"))

                    _moduleSrc = os.path.join(workspace.getGeneratedPath(), "modules", cm.name)
                    _moduleDst = os.path.join(t, "modules", cm.name)
                    if os.path.exists(_moduleDst):
                        os.unlink(_moduleDst)
                    os.symlink(_moduleSrc, _moduleDst) # Make links for Eclipse

                    for _r1 in m.requiredPackages:
                        for _r2 in workspace.packagesWorkspaceDependencies:
                            if True or (_r1 == _r2.name):
                                _packageSrc = os.path.join(workspace.getGeneratedPath(), "packages", _r1)
                                _packageDst = os.path.join(t, "packages", _r1)
                                if os.path.exists(_packageDst):
                                    os.unlink(_packageDst)
                                os.symlink(_packageSrc, _packageDst) # Make links for Eclipse

                    for _r1 in cm.requiredPackages:
                        _packageSrc = os.path.join(workspace.getGeneratedPath(), "packages", _r1)
                        _packageDst = os.path.join(t, "packages", _r1)
                        if os.path.exists(_packageDst):
                            os.unlink(_packageDst)
                        os.symlink(_packageSrc, _packageDst)  # Make links for Eclipse
                    # ECLIPSE WORKAROUND END


                    (source, dummy) = os.path.split(m.source)

                    cmake_cmd = cmakeCommand(cm.chip, source)

                    if(not mustGenerate):
                        table.append([CoreConsole.highlight(m.name), m.description, m.module, cm.chip, "Skipping..."])
                    else:
                        if(m.generate(t)):
                            table.append([CoreConsole.highlight(m.name), m.description, m.module, cm.chip, m.destination])
                        else:
                            table.append([CoreConsole.highlight(m.name), m.description, m.module, cm.chip, m.reason])


                    dest = os.path.join(workspace.getBuildPath(), m.name)
                    if not os.path.isdir(dest):
                        os.mkdir(dest)

                    try:
                        CoreConsole.info(Fore.MAGENTA + cmake_cmd + Fore.RESET)

                        out = subprocess.check_output(cmake_cmd, shell=True, cwd=dest)
                    except subprocess.CalledProcessError as outException:
                        CoreConsole.out("Failed")

                for m in workspace.invalidModuleTargets:
                    table.append([CoreConsole.error(m.filename), CoreConsole.error(m.reason), "", ""])

                if len(table) > 0:
                    CoreConsole.out(CoreConsole.h1("TARGETS"))
                    CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "CoreModule", "Chip", "Output"]))

            else:
                CoreConsole.out(CoreConsole.error(workspace.reason))

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
    except Exception as e:
        CoreConsole.out("Exception: " + CoreConsole.error(repr(e)))
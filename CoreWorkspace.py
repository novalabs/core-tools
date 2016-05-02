#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import subprocess

from Core import *
from CoreModule import generate as generateModule
from CorePackage import generate as generatePackage


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
        if self.root is None:  # Check for cached value
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
        if self.sources is None:  # Check for cached value
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
            if self.generated is None:  # Check for cached value
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
            if self.build is None:  # Check for cached value
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

    def open(self, root = None, coreRoot = None):  # If root is None it will use CWD
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

        return self.requiredModules

    def getRequiredPackages(self):
        tmp = []
        for x in self.validModuleTargets:
            for y in x.requiredPackages:
                tmp.append(y)

            m = self.core.getModuleByName(x.module)
            if m is not None:
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
    buffer.append('  "description": "Workspace"')
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
    mm = ["ls", "generate", "init", "target"]
    return (m for m in mm if m.startswith(prefix))


def target_action_completer(prefix, parsed_args, **kwargs):
    mm = ["add"]
    return (m for m in mm if m.startswith(prefix))

def module_completer(prefix, parsed_args, **kwargs):
    if parsed_args.action is not None:
        coreRoot = os.environ.get("NOVA_CORE_ROOT")
        if coreRoot is not None:
            mm = listDirectories(os.path.join(coreRoot, "modules"))  # TODO ...
            return (m for m in mm if m.startswith(prefix))


def ls(srcPath, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    workspace = CoreWorkspace()
    workspace.open(coreRoot=NOVA_CORE_ROOT)

    CoreConsole.out(CoreConsole.h1("WORKSPACE"))

    if not workspace.opened:
        CoreConsole.out(CoreConsole.error(workspace.reason))
        printSuccessOrFailure(False)
        return -1

    table = []
    for m in workspace.validModuleTargets:
        table.append(m.getSummary(workspace.getRoot()))

    for m in workspace.invalidModuleTargets:
        table.append(m.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h2("TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ModuleTarget.getSummaryFields()))

    table = []
    for p in workspace.validPackages:
        table.append(p.getSummary(workspace.getRoot()))

    for p in workspace.invalidPackages:
        table.append(p.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGES"))
        CoreConsole.out(CoreConsole.table(table, CorePackage.getSummaryFields()))

    table = workspace.getPackagesDependenciesSummary()
    if len(table) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGE DEPENDENCIES"))
        CoreConsole.out(CoreConsole.table(table, CoreWorkspace.getPackagesDependenciesSummaryFields()))

    table = workspace.getModulesDependenciesSummary()
    if len(table) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MODULE DEPENDENCIES"))
        CoreConsole.out(CoreConsole.table(table, CoreWorkspace.getModulesDependenciesSummaryFields()))

    if not workspace.checkPackagesDependencies():
        CoreConsole.out(CoreConsole.error("There are unmet Package dependencies: " + ", ".join(workspace.packagesNoneDependencies)))
        CoreConsole.out("")
        isOk = False

    if not workspace.checkModulesDependencies():
        CoreConsole.out(CoreConsole.error("There are unmet Module dependencies: " + ", ".join(workspace.modulesNoneDependencies)))
        CoreConsole.out("")
        isOk = False

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def generate(srcPath, dstPath, force, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    workspace = CoreWorkspace()
    workspace.open(coreRoot=NOVA_CORE_ROOT)

    CoreConsole.out(CoreConsole.h1("WORKSPACE"))

    if not workspace.opened:
        CoreConsole.out(CoreConsole.error(workspace.reason))
        printSuccessOrFailure(False)
        return -1

    if not workspace.checkPackagesDependencies():
        CoreConsole.out(CoreConsole.error("There are unmet Package dependencies: " + ", ".join(workspace.packagesNoneDependencies)))
        CoreConsole.out("")
        isOk = False

    if not workspace.checkModulesDependencies():
        CoreConsole.out(CoreConsole.error("There are unmet Module dependencies: " + ", ".join(workspace.modulesNoneDependencies)))
        CoreConsole.out("")
        isOk = False

    if force:
        isOk = True

    if not isOk:  # Don't go any further...
        printSuccessOrFailure(False)
        return -1

# --- DEPS --------------------------------------------------------------------

    table = []
    for x in workspace.packagesCoreDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Core Package dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
        res = generatePackage(os.path.join(workspace.core.getPackagesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "packages"), True, args.verbose)
        if res != 0:
            isOk = False
            CoreConsole.out(str(res))
        CoreConsole.out('')

    for x in workspace.packagesWorkspaceDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Workspace Package dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
        res = generatePackage(os.path.join(workspace.getPackagesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "packages"), True, args.verbose)
        if res != 0:
            isOk = False
            CoreConsole.out(str(res))
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
            CoreConsole.out(str(res))
        CoreConsole.out('')

    for x in workspace.modulesWorkspaceDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Workspace Module dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
        res = generateModule(os.path.join(workspace.getModulesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "modules"), True, args.verbose)
        if res != 0:
            isOk = False
            CoreConsole.out(str(res))
        CoreConsole.out('')

    for x in workspace.modulesNoneDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Module dependency: " + Style.BRIGHT + x + Style.RESET_ALL)
        CoreConsole.out(CoreConsole.error("404 not found"))
        CoreConsole.out('')

# --- NOW THE TARGETS ---------------------------------------------------------

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
                    if line.startswith("## TARGET MODULE"):  # Grep marker in file
                        grepped = True
                        break

        if exists and not grepped:
            mustGenerate = False

        cm = workspace.core.getModuleByName(m.module)  # Find the required core module,,,
        if cm is None:
            cm = workspace.getModuleByName(m.module)

# ECLIPSE WORKAROUND BEGIN
        if not os.path.isdir(os.path.join(t, "modules")):
            os.mkdir(os.path.join(t, "modules"))

        if not os.path.isdir(os.path.join(t, "packages")):
            os.mkdir(os.path.join(t, "packages"))

        moduleSrc = os.path.join(workspace.getGeneratedPath(), "modules", cm.name)
        moduleDst = os.path.join(t, "modules", cm.name)
        if os.path.exists(moduleDst):
            os.unlink(moduleDst)
        os.symlink(moduleSrc, moduleDst)  # Make links for Eclipse

        for package in m.requiredPackages:  # Link the target required packages
            packageSrc = os.path.join(workspace.getGeneratedPath(), "packages", package)
            packageDst = os.path.join(t, "packages", package)
            if os.path.exists(packageDst):
                os.unlink(packageDst)
            os.symlink(packageSrc, packageDst)  # Make links for Eclipse

        for package in cm.requiredPackages:  # Link the module required packages
            packageSrc = os.path.join(workspace.getGeneratedPath(), "packages", package)
            packageDst = os.path.join(t, "packages", package)
            if os.path.exists(packageDst):
                os.unlink(packageDst)
            os.symlink(packageSrc, packageDst)  # Make links for Eclipse
# ECLIPSE WORKAROUND END

        executeCmake = True
        if mustGenerate:
            m.generate(t)
            if not m.generated:
                executeCmake = False
                isOk = False

        dest = os.path.join(workspace.getBuildPath(), m.name)
        if not os.path.isdir(dest):
            os.mkdir(dest)

        cmakeSuccess = True
        if executeCmake:
            (source, dummy) = os.path.split(m.source)

            cmake_cmd = cmakeCommand(cm.chip, source)

            try:
                CoreConsole.info(Fore.MAGENTA + cmake_cmd + Fore.RESET)

                out = subprocess.check_output(cmake_cmd, shell=True, cwd=dest)
                if verbose:
                    CoreConsole.out(out)
            except subprocess.CalledProcessError as outException:
                CoreConsole.out("CMake subprocess failed")
                cmakeSuccess = False
                isOk = False

        dest = os.path.relpath(dest, workspace.getRoot())

        if m.generated:
            if cmakeSuccess:
                table.append([CoreConsole.highlight(m.name), m.description, m.module, cm.chip, os.path.relpath(m.destination, workspace.getRoot()), dest, "Success"])
            else:
                table.append([CoreConsole.highlight(m.name), m.description, m.module, cm.chip, os.path.relpath(m.destination, workspace.getRoot()), dest, CoreConsole.error("CMake error... Try executing with --verbose")])
        else:
            table.append([CoreConsole.highlight(m.name), m.description, m.module, cm.chip, m.reason, dest, ""])

    for m in workspace.invalidModuleTargets:
        table.append([CoreConsole.error(m.filename), CoreConsole.error(m.reason), "", "", ""])

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h1("TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ["Name", "Description", "CoreModule", "Chip", "Output", "Build", "CMake"]))

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def initialize(force, verbose):
    workspace = CoreWorkspace()

    isOk = True

    try:
        root = os.getcwd()

        if workspace.getRoot(root) is not None:
            if not force:
                CoreConsole.out(CoreConsole.error("Workspace already initialized"))
                return -1
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
        mkdir(os.path.join(root, "sources", "targets"))
        mkdir(os.path.join(root, "sources", "packages"))
        mkdir(os.path.join(root, "generated"))
        mkdir(os.path.join(root, "generated", "modules"))
        mkdir(os.path.join(root, "generated", "packages"))
        mkdir(os.path.join(root, "build"))

        CoreConsole.out("Workspace initialized.")
        CoreConsole.out("You can now do a 'source setup.sh'")
    except IOError as e:
        CoreConsole.out(CoreConsole.error(str(e.strerror) + " [" + CoreConsole.highlightFilename(e.filename) + "]"))
        isOk = False

    CoreConsole.out("")

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def target_add(module_name, name):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    workspace = CoreWorkspace()
    workspace.open(coreRoot=NOVA_CORE_ROOT)

    if not workspace.opened:
        CoreConsole.out(CoreConsole.error(workspace.reason))
        printSuccessOrFailure(False)
        return -1

    for target in workspace.validModuleTargets:
        if target.name == name:
            CoreConsole.out(CoreConsole.error("Target '" + name +  "' already defined"))
            CoreConsole.out("")
            printSuccessOrFailure(False)
            return -1

    target_root = os.path.join(workspace.getModuleTargetsRoot(), name)

    if os.path.isdir(target_root):
        shutil.rmtree(target_root)

    module = workspace.getModuleByName(module_name)
    if module is not None:
        CoreConsole.out("Using Workspace module '" + module_name + "'")
    else:
        module = workspace.core.getModuleByName(module_name)
        if module is not None:
            CoreConsole.out("Using Core module '" + module_name + "'")
        else:
            CoreConsole.out(CoreConsole.error("Module '" + module_name + "' does not exists"))
            CoreConsole.out("")
            printSuccessOrFailure(False)
            return -1

#TODO Add some error handling

    shutil.copytree(os.path.join(module.moduleRoot, "target_template"), target_root)

    src = open(os.path.join(target_root, "MODULE_TARGET.json"))
    json = src.read()
    src.close()

    json = json.replace("@@NAME@@", name)
    json = json.replace("@@DESCRIPTION@@", name)

    sink = open(os.path.join(target_root, "MODULE_TARGET.json"), 'w')
    sink.write(json)
    sink.close()

    CoreConsole.out("")
    printSuccessOrFailure(True)
    return 0

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

        parser_target = subparsers.add_parser('module', help='Workspace Targets management')

        subparsers_target = parser_target.add_subparsers(help='Sub command help', dest='target_action')

        parser_target_add = subparsers_target.add_parser('add', help='Add a target to the workspace')

        parser_target_add.add_argument("core_module", nargs=1, help="Module [default = None]", default=None).completer = module_completer
        parser_target_add.add_argument("name", nargs=1, help="Target name [default = None]", default=None)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        retval = 0

        verbose = args.verbose

        if not verbose:
            CoreConsole.debug = False
            CoreConsole.verbose = False

        if args.action == "initialize":
            force = args.force

            retval = initialize(force, verbose)

        if args.action == "ls":
            retval = ls(None, verbose)

        if args.action == "generate":
            force = args.force

            retval = generate(None, None, force, verbose)

        if args.action == "module":
            module_name = args.core_module[0]
            targetName = args.name[0]

            retval = target_add(module_name, targetName)

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1)

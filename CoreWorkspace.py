#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import argparse
import argcomplete

import subprocess

from novalabs.core.CoreWorkspace import *
from CoreModule import generate as generateModule
from CorePackage import generate as generatePackage
import novalabs.generators as generators


# ENVIRONMENT VARIABLES -------------------------------------------------------

NOVA_CORE_ROOT = os.environ.get("NOVA_CORE_ROOT")
if NOVA_CORE_ROOT is None:
    CoreConsole.out(CoreConsole.error("NOVA_CORE_ROOT environment variable not found"))
    sys.exit(-1)

NOVA_CORE_TOOLCHAIN = os.environ.get("NOVA_CORE_TOOLCHAIN")
if NOVA_CORE_TOOLCHAIN is None:
    CoreConsole.out(CoreConsole.error("NOVA_CORE_TOOLCHAIN environment variable not found"))
    sys.exit(-1)

NOVA_CHIBIOS_16_ROOT = os.environ.get("NOVA_CHIBIOS_16_ROOT")
if NOVA_CHIBIOS_16_ROOT is None:
    CoreConsole.out(CoreConsole.warning("NOVA_CHIBIOS_16_ROOT environment variable not found, will check later if we really need it"))

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


def cmakeCommand(chip, source, buildType, OSVersion="CHIBIOS_3", workspaceRoot=NOVA_WORKSPACE_ROOT):
    cmake_cmd = "cmake --verbose"
    cmake_cmd += " -DSTM32_CHIP=" + chip
    cmake_cmd += " -DCMAKE_TOOLCHAIN_FILE=" + os.path.join(CMAKE_PREFIX_PATH, "gcc_stm32.cmake")
    cmake_cmd += " -DCMAKE_BUILD_TYPE=" + buildType
    cmake_cmd += " -DTOOLCHAIN_PREFIX=" + NOVA_CORE_TOOLCHAIN
    cmake_cmd += " -DCMAKE_MODULE_PATH=" + CMAKE_MODULE_PATH
    if OSVersion == "CHIBIOS_3":
        cmake_cmd += " -DCHIBIOS_ROOT=" + NOVA_CHIBIOS_ROOT
    elif OSVersion == "CHIBIOS_16":
        if NOVA_CHIBIOS_16_ROOT is None:
            CoreConsole.out(CoreConsole.error("NOVA_CHIBIOS_16_ROOT environment variable not found, and we really need it"))
            sys.exit(-1)
        cmake_cmd += " -DCHIBIOS_ROOT=" + NOVA_CHIBIOS_16_ROOT

    cmake_cmd += " -DNOVA_ROOT=" + NOVA_CORE_ROOT
    cmake_cmd += " -DNOVA_WORKSPACE_ROOT=" + workspaceRoot
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


def writeSetupSh(root):
    buffer = []

    buffer.append('source ' + os.path.join(NOVA_CORE_ROOT, "setup.sh"))
    buffer.append('export NOVA_WORKSPACE_ROOT=' + root)
    buffer.append('')

    sink = open(os.path.join(root, "setup.sh"), 'w')
    sink.write("\n".join(buffer))


def writeSetupBat(root):
    buffer = []

    buffer.append('@echo off')
    buffer.append(os.path.join(NOVA_CORE_ROOT, "setup.bat"))
    buffer.append('set NOVA_WORKSPACE_ROOT=' + root)
    buffer.append('')

    sink = open(os.path.join(root, "setup.bat"), 'w')
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


def build_type_completer(prefix, parsed_args, **kwargs):
    mm = ["debug", "release", "minsizerel"]
    return (m for m in mm if m.startswith(prefix))


def ls(srcPath, verbose):
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    workspace = Workspace()
    workspace.open(coreRoot=NOVA_CORE_ROOT, workspaceRoot=NOVA_WORKSPACE_ROOT)
    CoreConsole.out(CoreConsole.h1("WORKSPACE"))

    if not workspace.isValid():
        CoreConsole.out(CoreConsole.error(workspace.reason))
        printSuccessOrFailure(False)
        return -1

    # MODULES
    table = []
    for m in workspace.coreWorkspace.validModules:
        table.append(m.getSummary(workspace.getRoot()))

    for m in workspace.coreWorkspace.invalidModules:
        table.append(m.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h2("MODULES"))
        CoreConsole.out(CoreConsole.table(table, CoreModule.getSummaryFields()))

    # PACKAGES
    table = []
    for p in workspace.coreWorkspace.validPackages:
        table.append(p.getSummary(workspace.getRoot()))

    for p in workspace.coreWorkspace.invalidPackages:
        table.append(p.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGES"))
        CoreConsole.out(CoreConsole.table(table, CorePackage.getSummaryFields()))

    # PARAMETERS
    table = []
    for m in workspace.validParameters():
        table.append(m.getSummary(workspace.getRoot()))

    for m in workspace.invalidParameters():
        table.append(m.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h2("PARAMETERS"))
        CoreConsole.out(CoreConsole.table(table, ModuleTarget.getSummaryFields()))

    # PACKAGE DEPENDENCIES
    table = workspace.getPackagesDependenciesSummary()
    if len(table) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("PACKAGE DEPENDENCIES"))
        CoreConsole.out(CoreConsole.table(table, Workspace.getPackagesDependenciesSummaryFields()))

    # MODULE DEPENDENCIES
    table = workspace.getModulesDependenciesSummary()
    if len(table) > 0:
        CoreConsole.out("")
        CoreConsole.out(CoreConsole.h2("MODULE DEPENDENCIES"))
        CoreConsole.out(CoreConsole.table(table, Workspace.getModulesDependenciesSummaryFields()))

    if not workspace.checkPackagesDependencies():
        CoreConsole.out(CoreConsole.error("There are unmet Package dependencies: " + ", ".join(workspace.packagesNoneDependencies)))
        CoreConsole.out("")
        isOk = False

    if not workspace.checkModulesDependencies():
        CoreConsole.out(CoreConsole.error("There are unmet Module dependencies: " + ", ".join(workspace.modulesNoneDependencies)))
        CoreConsole.out("")
        isOk = False

    # MODULE TARGETS
    table = []
    for m in workspace.validModuleTargets():
        table.append(m.getSummary(workspace.getRoot()))

    for m in workspace.invalidModuleTargets():
        table.append(m.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h2("MODULE TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ModuleTarget.getSummaryFields()))

    # PARAMETER TARGETS
    table = []
    for m in workspace.validParameterTargets():
        table.append(m.getSummary(workspace.getRoot()))

    for m in workspace.invalidParameterTargets():
        table.append(m.getSummary(workspace.getRoot()))
        isOk = False

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h2("PARAMETER TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ParametersTarget.getSummaryFields()))

    printSuccessOrFailure(isOk)

    if isOk:
        return 0
    else:
        return -1


def generate(srcPath, dstPath, buildTypes, force, verbose):
    # I know that the following is a huge heap of crap, so please do not complain about it.
    if not verbose:
        CoreConsole.debug = False
        CoreConsole.verbose = False

    isOk = True

    workspace = Workspace()
    workspace.open(coreRoot=NOVA_CORE_ROOT, workspaceRoot=NOVA_WORKSPACE_ROOT)

    CoreConsole.out(CoreConsole.h1("WORKSPACE"))

    if not workspace.isValid():
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
        res = generatePackage(os.path.join(workspace.core.getPackagesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "packages"), True, args.verbose, False, None, workspace.getRoot())
        if res != 0:
            isOk = False
            CoreConsole.out(str(res))
        CoreConsole.out('')

    for x in workspace.packagesWorkspaceDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Workspace Package dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
        res = generatePackage(os.path.join(workspace.getPackagesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "packages"), True, args.verbose, True, workspace.getRoot(), workspace.getRoot())
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
        res = generateModule(os.path.join(workspace.core.getModulesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "modules"), True, args.verbose, False, None, workspace.getRoot())
        if res != 0:
            isOk = False
            CoreConsole.out(str(res))
        CoreConsole.out('')

    for x in workspace.modulesWorkspaceDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Workspace Module dependency: " + Style.BRIGHT + x.name + Style.RESET_ALL)
        res = generateModule(os.path.join(workspace.coreWorkspace.getModulesRoot(), x.name), os.path.join(workspace.getGeneratedPath(), "modules"), True, args.verbose, True, workspace.getRoot(), workspace.getRoot())
        if res != 0:
            isOk = False
            CoreConsole.out(str(res))
        CoreConsole.out('')

    for x in workspace.modulesNoneDependencies:
        CoreConsole.out(Fore.MAGENTA + "Generating Module dependency: " + Style.BRIGHT + x + Style.RESET_ALL)
        CoreConsole.out(CoreConsole.error("404 not found"))
        CoreConsole.out('')

    # --- NOW THE TARGETS ---------------------------------------------------------

    table = []
    for p in workspace.validParameterTargets():
        p.generate(workspace, os.path.join(workspace.getGeneratedPath(), "params"), os.path.join(workspace.getBuildPath(), "params"))
        table.append(p.getSummaryGenerate(workspace.getRoot(), workspace.getRoot()))

        if not p.generated:
            isOk = False

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h1("GENERATED PARAMETERS TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ParametersTarget.getSummaryFieldsGenerate()))

    table = []
    for m in workspace.validModuleTargets():
        targetSuccess = True

        target_root = os.path.join(workspace.getSourcesPath(), "targets", m.name)

        mustGenerate = True
        exists = False
        grepped = False

        if os.path.isdir(target_root):
            t2 = os.path.join(target_root, "CMakeLists.txt")
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
            cm = workspace.coreWorkspace.getModuleByName(m.module)

        # ECLIPSE WORKAROUND BEGIN
        eclipse_workaround = os.environ.get("NOVA_CORE_ECLIPSE_LINK_FILES")

        if eclipse_workaround is not None:
            if not os.path.isdir(os.path.join(target_root, "modules")):
                os.mkdir(os.path.join(target_root, "modules"))

            if not os.path.isdir(os.path.join(target_root, "packages")):
                os.mkdir(os.path.join(target_root, "packages"))

            moduleSrc = os.path.join(workspace.getGeneratedPath(), "modules", cm.name)
            moduleDst = os.path.join(target_root, "modules", cm.name)
            CoreConsole.info("Eclipse link: " + moduleSrc + " > " + moduleDst)

            if os.path.exists(moduleDst) and os.path.islink(moduleDst):
                os.remove(moduleDst)

            os.symlink(moduleSrc, moduleDst)  # Make links for Eclipse

            for package in m.requiredPackages:  # Link the target required packages
                packageSrc = os.path.join(workspace.getGeneratedPath(), "packages", package)
                packageDst = os.path.join(target_root, "packages", package)
                CoreConsole.info("Eclipse link: " + packageSrc + " " + packageDst)

                if os.path.exists(packageDst) and os.path.islink(packageDst):
                    os.remove(packageDst)

                os.symlink(packageSrc, packageDst)  # Make links for Eclipse

            for package in cm.requiredPackages:  # Link the module required packages
                packageSrc = os.path.join(workspace.getGeneratedPath(), "packages", package)
                packageDst = os.path.join(target_root, "packages", package)
                CoreConsole.info("Eclipse link: " + packageSrc + " " + packageDst)

                if os.path.exists(packageDst) and os.path.islink(packageDst):
                    os.remove(packageDst)

                os.symlink(packageSrc, packageDst)  # Make links for Eclipse
                # ECLIPSE WORKAROUND END

        executeCmake = True

        gen = generators.ModuleTargetGenerator(m)

        gen.generate(target_root, not mustGenerate)
        if gen.generated:
            fields = [CoreConsole.highlight(m.name), m.description, m.module, cm.chip, m.os_version, os.path.relpath(gen.destination, workspace.getRoot()), str(mustGenerate)]
            headers = ["Name", "Description", "CoreModule", "Chip", "OS Version", "CMakeLists", "Generated CMakeLists"]
        else:
            executeCmake = False
            isOk = False
            targetSuccess = False
            fields = [CoreConsole.highlight(m.name), m.description, m.module, cm.chip, m.os_version, CoreConsole.error(m.reason), str(mustGenerate)]
            headers = ["Name", "Description", "CoreModule", "Chip", "OS Version", "CMakeLists", "Generated CMakeLists"]

        for buildType in buildTypes:
            headers += ["Build (" + buildType + ")", "CMake (" + buildType + ")"]

            if gen.generated:
                dest = os.path.join(workspace.getBuildPath(), buildType)
                if not os.path.isdir(dest):
                    os.mkdir(dest)
                dest = os.path.join(workspace.getBuildPath(), buildType, m.name)
                if not os.path.isdir(dest):
                    os.mkdir(dest)

                if executeCmake:
                    (source, dummy) = os.path.split(m.source)

                    cmake_cmd = cmakeCommand(cm.chip, source, buildType, m.os_version, workspace.getRoot())

                    try:
                        CoreConsole.info(Fore.MAGENTA + cmake_cmd + Fore.RESET)

                        out = subprocess.check_output(cmake_cmd, shell=True, cwd=dest)
                        if verbose:
                            CoreConsole.out(out)

                        fields += [os.path.relpath(dest, workspace.getRoot()), "OK"]
                    except subprocess.CalledProcessError as e:
                        CoreConsole.out("CMake subprocess failed")
                        isOk = False
                        targetSuccess = False
                        fields += [os.path.relpath(dest, workspace.getRoot()), CoreConsole.error("CMake error. Try with --verbose")]
                    except BaseException as e:
                        fields += [os.path.relpath(dest, workspace.getRoot()), CoreConsole.error("Unexpected error: " + repr(e))]
                        isOk = False
                        targetSuccess = False
            else:
                fields += ["---", "---"]
        try:
            eclipse_template = os.path.join(cm.moduleRoot, "eclipse_template")
            if os.path.isdir(eclipse_template):
                if not os.path.exists(os.path.join(target_root, ".project")):
                    src = open(os.path.join(eclipse_template, ".project"))
                    data = src.read()
                    src.close()
                    data = data.replace("@@NAME@@", m.name)
                    sink = open(os.path.join(target_root, ".project"), 'w')
                    sink.write(data)
                    sink.close()

                if not os.path.exists(os.path.join(target_root, ".cproject")):
                    src = open(os.path.join(eclipse_template, ".cproject"))
                    data = src.read()
                    src.close()
                    data = data.replace("@@NAME@@", m.name)
                    data = data.replace("@@NOVA_CORE_ROOT@@", NOVA_CORE_ROOT)
                    sink = open(os.path.join(target_root, ".cproject"), 'w')
                    sink.write(data)
                    sink.close()

                tmp = "@@NAME@@-Debug.launch".replace("@@NAME@@", m.name)
                if not os.path.exists(os.path.join(target_root, tmp)):
                    src = open(os.path.join(eclipse_template, "@@NAME@@-Debug.launch"))
                    data = src.read()
                    src.close()
                    data = data.replace("@@NAME@@", m.name)
                    data = data.replace("@@BUILD_PATH@@", workspace.getBuildPath())
                    data = data.replace("@@NOVA_CORE_TOOLCHAIN@@", NOVA_CORE_TOOLCHAIN)
                    sink = open(os.path.join(target_root, tmp), 'w')
                    sink.write(data)
                    sink.close()

                tmp = "@@NAME@@-Release.launch".replace("@@NAME@@", m.name)
                if not os.path.exists(os.path.join(target_root, tmp)):
                    src = open(os.path.join(eclipse_template, "@@NAME@@-Release.launch"))
                    CoreConsole.info("Template " + repr(src))
                    data = src.read()
                    src.close()
                    data = data.replace("@@NAME@@", m.name)
                    data = data.replace("@@BUILD_PATH@@", workspace.getBuildPath())
                    data = data.replace("@@NOVA_CORE_TOOLCHAIN@@", NOVA_CORE_TOOLCHAIN)
                    sink = open(os.path.join(target_root, tmp), 'w')
                    sink.write(data)
                    sink.close()

                fields += ["OK"]
                headers += ["Eclipse files"]
            else:
                fields += ["Skip"]
                headers += ["Eclipse files"]
        except IOError as e:
            fields += [CoreConsole.error(str(e.strerror) + " [" + CoreConsole.highlightFilename(e.filename) + "]")]
            headers += ["Eclipse files"]
            targetSuccess = False

        if targetSuccess:
            fields += [CoreConsole.success("OK")]
            headers += ["Status"]
        else:
            fields += [CoreConsole.fail("FAIL")]
            headers += ["Status"]

        table.append(fields)

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h1("GENERATED MODULE TARGETS"))
        CoreConsole.out(CoreConsole.table(table, headers))

    # INVALID STUFF
    table = []
    for m in workspace.invalidModuleTargets():
        table.append(m.getSummary(workspace.getRoot()))

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h1("INVALID MODULE TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ModuleTarget.getSummaryFields()))
        isOk = False

    table = []
    for p in workspace.invalidParameterTargets():
        table.append(p.getSummary(workspace.getRoot()))

    if len(table) > 0:
        CoreConsole.out(CoreConsole.h1("INVALID PARAMETERS TARGETS"))
        CoreConsole.out(CoreConsole.table(table, ParametersTarget.getSummaryFields()))
        isOk = False

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
                if os.name != 'nt':
                    tmp = os.path.join(root, "setup.sh")
                    if os.path.isfile(tmp):
                        os.unlink(tmp)
                else:
                    tmp = os.path.join(root, "setup.bat")
                    if os.path.isfile(tmp):
                        os.unlink(tmp)

        # create WORKSPACE.json
        createJSON(root)

        # create directories
        mkdir(os.path.join(root, "src"))
        mkdir(os.path.join(root, "src", "targets"))
        mkdir(os.path.join(root, "src", "packages"))
        mkdir(os.path.join(root, "src", "modules"))
        mkdir(os.path.join(root, "src", "params"))
        mkdir(os.path.join(root, "generated"))
        mkdir(os.path.join(root, "generated", "modules"))
        mkdir(os.path.join(root, "generated", "packages"))
        mkdir(os.path.join(root, "generated", "params"))
        mkdir(os.path.join(root, "build"))
        mkdir(os.path.join(root, "build", "debug"))
        mkdir(os.path.join(root, "build", "release"))
        mkdir(os.path.join(root, "build", "params"))

        CoreConsole.out("Workspace initialized.")

        # create setup.sh
        if os.name != 'nt':
            writeSetupSh(root)
            CoreConsole.out("You can now do a 'source setup.sh'")
        else:
            writeSetupBat(root)
            CoreConsole.out("You can now execute 'setup.bat'")

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

    workspace = Workspace()
    workspace.open(coreRoot=NOVA_CORE_ROOT, workspaceRoot=NOVA_WORKSPACE_ROOT)

    if not workspace.isValid():
        CoreConsole.out(CoreConsole.error(workspace.reason))
        printSuccessOrFailure(False)
        return -1

    for target in workspace.validModuleTargets():
        if target.name == name:
            CoreConsole.out(CoreConsole.error("Target '" + name + "' already defined"))
            CoreConsole.out("")
            printSuccessOrFailure(False)
            return -1

    target_root = os.path.join(workspace.getModuleTargetsRoot(), name)
    default_params_root = os.path.join(workspace.getParametersTargetsRoot(), name)

    if os.path.isdir(target_root):
        shutil.rmtree(target_root)

    module = workspace.coreWorkspace.getModuleByName(module_name)
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

            # TODO Add some error handling

            # ----------------------------------------------------------------------------------------------------------------------
    shutil.copytree(os.path.join(module.moduleRoot, "target_template"), target_root)

    src = open(os.path.join(target_root, "MODULE_TARGET.json"))
    json = src.read()
    src.close()
    json = json.replace("@@NAME@@", name)
    json = json.replace("@@DESCRIPTION@@", name)
    sink = open(os.path.join(target_root, "MODULE_TARGET.json"), 'w')
    sink.write(json)
    sink.close()

    if os.path.isfile(os.path.join(target_root, "PARAMETERS.json")):
        src = open(os.path.join(target_root, "PARAMETERS.json"))
        json = src.read()
        src.close()
        json = json.replace("@@NAME@@", name)
        sink = open(os.path.join(target_root, "PARAMETERS.json"), 'w')
        sink.write(json)
        sink.close()

        default_params_file = os.path.join(module.moduleRoot, "target_template", "PARAMETERS.default.json")

        if os.path.isfile(default_params_file):
            src = open(default_params_file)
            json = src.read()
            src.close()
            json = json.replace("@@NAME@@", name)

            if not os.path.isdir(default_params_root):
                mkdir(default_params_root)
            sink = open(os.path.join(default_params_root, "default.json"), 'w+')
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
        parser_gen.add_argument("build_type", nargs='?', help="Build type [default = debug]", default=None).completer = build_type_completer
        parser_gen.add_argument("--force", help="Generate even in presence on unmet dependencies [default = False]", action="store_true", default=False)

        parser_init = subparsers.add_parser('initialize', help='Initializes a Workspace')
        parser_init.add_argument("--force", help="Re-Initialize [default = False]", action="store_true", default=False)

        parser_target = subparsers.add_parser('target', help='Workspace Targets management')

        subparsers_target = parser_target.add_subparsers(help='Sub command help', dest='target_action')

        parser_target_add = subparsers_target.add_parser('add', help='Add a target to the workspace')

        parser_target_add.add_argument("core_module", nargs=1, help="Module [default = None]", default=None).completer = module_completer
        parser_target_add.add_argument("name", nargs=1, help="Target name [default = None]", default=None)

        parser_target_add = subparsers_target.add_parser('rm', help='Remove a target to the workspace')

        parser_target_add.add_argument("name", nargs=1, help="Target name [default = None]", default=None)

        argcomplete.autocomplete(parser)
        args = parser.parse_args()

        retval = 0

        if args.action is None:
            sys.exit(-1)

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
            if args.build_type is None:
                buildTypes = ["debug", "release"]
            else:
                buildTypes = [args.build_type]

            retval = generate(None, None, buildTypes, force, verbose)

        if args.action == "target":
            if args.target_action == "add":
                module_name = args.core_module[0]
                targetName = args.name[0]

                retval = target_add(module_name, targetName)
            elif args.target_action == "rm":
                CoreConsole.out("Would you like to have this command implemented? Let me know!")

        sys.exit(retval)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1)

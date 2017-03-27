# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .Core import *
from .ModuleTarget import *
from .ParametersTarget import *
from abc import abstractmethod


class CoreWorkspaceBase:
    def __init__(self):
        self.sources = None
        self.generated = None
        self.build = None

    @abstractmethod
    def getCorePackage(self, name):
        pass

    @abstractmethod
    def getCoreModule(self, name):
        pass

    @abstractmethod
    def getCoreConfiguration(self, package, name):
        pass

    @abstractmethod
    def getCoreMessage(self, package, name):
        pass

    @abstractmethod
    def getRoot(self, cwd=None):
        pass

    @abstractmethod
    def isValid(self):
        pass

    def getRoot(self, cwd=None):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("WORKSPACE.json", cwd)
            if self.root is not None:
                CoreConsole.ok("CoreWorkspace::getRoot: Workspace found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "CoreWorkspace::getRoot: Not inside a Workspace"
                CoreConsole.fail(self.reason)

        return self.root

    def getSourcesPath(self):
        if self.sources is None:  # Check for cached value
            if self.getRoot() is not None:
                tmp = os.path.join(self.getRoot(), "src")
                if os.path.isdir(tmp):
                    self.sources = tmp
                else:
                    raise CoreError("'src' directory not found inside Workspace", context="CoreWorkspaceBase::getSourcesPath")
            else:
                self.sources = None

        return self.sources

    def getGeneratedPath(self):
        if self.generated is None:  # Check for cached value
            if self.getRoot() is not None:
                tmp = os.path.join(self.getRoot(), "generated")
                if not os.path.isdir(tmp):
                    try:
                        os.makedirs(tmp)
                    except OSError as e:
                        raise CoreError("I/0 Error: " + str(e.strerror), e.filename, context="CoreWorkspaceBase::getGeneratedPath")
                self.generated = tmp
            else:
                self.generated = None

        return self.generated

    def getBuildPath(self):
        if self.build is None:  # Check for cached value
            if self.getRoot() is not None:
                tmp = os.path.join(self.getRoot(), "build")
                if not os.path.isdir(tmp):
                    try:
                        os.makedirs(tmp)
                    except OSError as e:
                        raise CoreError("I/0 Error: " + str(e.strerror), e.filename, context="CoreWorkspaceBase::getBuildPath")
                self.build = tmp
            else:
                self.build = None

        return self.build

    def getPackagesRoot(self):
        if not self.isValid():
            raise CoreError("invalid", context="CoreWorkspaceBase::getPackagesRoot")
        return os.path.join(self.getSourcesPath(), "packages")

    def getModulesRoot(self):
        if not self.isValid():
            raise CoreError("invalid", context="CoreWorkspaceBase::getModulesRoot")
        return os.path.join(self.getSourcesPath(), "modules")

    def getModuleTargetsRoot(self):
        if not self.isValid():
            raise CoreError("invalid", context="CoreWorkspaceBase::getModuleTargetsRoot")
        return os.path.join(self.getSourcesPath(), "targets")

    def getParametersRoot(self):
        if not self.isValid():
            raise CoreError("invalid", context="CoreWorkspaceBase::getParametersRoot")
        return os.path.join(self.getSourcesPath(), "targets")

    def getParametersTargetsRoot(self):
        if not self.isValid():
            raise CoreError("invalid", context="CoreWorkspaceBase::getParametersTargetsRoot")
        return os.path.join(self.getSourcesPath(), "params")


class CoreWorkspace(CoreContainer, CoreWorkspaceBase):
    def __init__(self):
        CoreContainer.__init__(self)
        CoreWorkspaceBase.__init__(self)

        self._validModuleTargets = []
        self._invalidModuleTargets = []
        self._validParameters = []
        self._invalidParameters = []
        self._validParametersTargets = []
        self._invalidParametersTargets = []

        self.root = None
        self.sources = None
        self.generated = None
        self.build = None
        self.valid = False
        self.opened = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("WORKSPACE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.valid = True

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreWorkspace::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, root=None):
        self.valid = False

        try:
            if root is not None:
                self.root = root
            else:
                self.root = self.getRoot()

            if self.root is None:
                return False

            jsonFile = os.path.join(self.root, "WORKSPACE.json")

            if self.openJSON(jsonFile):
                self.openPackages()
                self.openModules()
                self.openModuleTargets()
                self.openParameters()
                self.openParametersTargets()

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreWorkspace::open: " + self.reason)
            return False

    def isValid(self):
        return self.valid

    # --- MODULE TARGET -----------------------------------------------------------
    def listModuleTargets(self):
        path = self.getModuleTargetsRoot()

        dirs = listDirectories(path, fullpath=True)

        tmp = []

        for x in dirs:
            if ModuleTarget.check(x):
                tmp.append(x)

        if tmp is not None:
            tmp.sort()

        return tmp

    def openModuleTargets(self):
        list = self.listModuleTargets()

        self._validModuleTargets = []
        self._invalidModuleTargets = []

        for x in list:
            m = ModuleTarget()
            if m.open(x):
                self._validModuleTargets.append(m)
            else:
                self._invalidModuleTargets.append(m)

        return self._validModuleTargets

    def getModuleTargetByName(self, name):
        if name is None:
            raise CoreError("CoreContainer::getModule() name is None")

        for x in self._validModuleTargets:
            if x.name == name:
                return x

        return None

    def validModuleTargets(self):
        return self._validModuleTargets

    def invalidModuleTargets(self):
        return self._invalidModuleTargets

    # --- PARAMETERS --------------------------------------------------------------
    def listParameters(self):
        path = self.getParametersRoot()

        dirs = listDirectories(path, fullpath=True)

        tmp = []

        for x in dirs:
            if Parameters.check(x):
                tmp.append(x)

        if tmp is not None:
            tmp.sort()

        return tmp

    def openParameters(self):
        list = self.listParameters()

        self._validParameters = []
        self._invalidParameters = []

        for x in list:
            m = Parameters()
            if m.open(x):
                self._validParameters.append(m)
            else:
                self._invalidParameters.append(m)

        return self._validParameters

    def getParameterByName(self, name):
        if name is None:
            raise CoreError("CoreContainer::getModule() name is None")

        for x in self._validParameters:
            if x.name == name:
                return x

        return None

    def validParameters(self):
        return self._validParameters

    def invalidParameters(self):
        return self._invalidParameters

    def listParametersTargets(self):
        path = self.getParametersTargetsRoot()

        dirs = listDirectories(path, fullpath=True)
        if dirs is not None:
            dirs.sort()

        tmp = []

        for d in dirs:
            files = listFilesByAndStripExtension(os.path.join(path, d), "json")
            if files is not None:
                files.sort()
            for f in files:
                tmp.append([d, f])

        return tmp

    def openParametersTargets(self):
        list = self.listParametersTargets()

        self._validParametersTargets = []
        self._invalidParametersTargets = []

        for x in list:
            m = ParametersTarget()
            if m.open(x[0], x[1]):
                self._validParametersTargets.append(m)
            else:
                self._invalidParametersTargets.append(m)

        return self._validParametersTargets

    def validParameterTargets(self):
        return self._validParametersTargets

    def invalidParameterTargets(self):
        return self._invalidParametersTargets


class Workspace(CoreWorkspaceBase):
    def __init__(self):
        self.root = None
        self.sources = None
        self.generated = None
        self.build = None
        self.valid = False
        self.reason = ""
        self.requiredModules = []
        self.requiredPackages = []

        self.core = Core()
        self.coreWorkspace = CoreWorkspace()

        self.packagesCoreDependencies = []
        self.packagesWorkspaceDependencies = []
        self.packagesNoneDependencies = []
        self.modulesWorkspaceDependencies = []
        self.modulesCoreDependencies = []
        self.modulesNoneDependencies = []

    def open(self, coreRoot=None, workspaceRoot=None):
        self.__init__()

        if not self.core.open(coreRoot):
            self.reason = self.core.reason
            return False
        else:
            if not self.coreWorkspace.open(self.getRoot(workspaceRoot)):
                self.reason = self.coreWorkspace.reason
                return False

        return True

    def isValid(self):
        return self.core.valid and self.coreWorkspace.valid

    def clean(self, force):
        root = self.getRoot()
        if root is not None:
            if not force:
                print("OK: " + root)
        else:
            print("!!!!")

    def validModuleTargets(self):
        return self.coreWorkspace.validModuleTargets()

    def invalidModuleTargets(self):
        return self.coreWorkspace.invalidModuleTargets()

    def validParameters(self):
        return self.coreWorkspace.validParameters()

    def invalidParameters(self):
        return self.coreWorkspace.invalidParameters()

    def validParameterTargets(self):
        return self.coreWorkspace.validParameterTargets()

    def invalidParameterTargets(self):
        return self.coreWorkspace.invalidParameterTargets()

    def getParameters(self, name) -> Parameters:
        for x in self.validParameters():
            if x.name == name:
                return x
        return None

    def getCoreConfiguration(self, package, name):
        p = self.getCorePackage(package)

        tmp = None

        if p is not None:
            tmp = CoreConfiguration()
            tmp.open(name, p)

        return tmp

    def getCoreMessage(self, package, name):
        p = self.getCorePackage(package)

        tmp = None

        if p is not None:
            tmp = CoreMessage()
            tmp.open(name, p)

        return tmp

    def getCorePackage(self, name):
        tmpW = self.coreWorkspace.getPackageByName(name)
        tmpC = self.core.getPackageByName(name)

        if tmpW is not None:
            return tmpW
        else:
            if tmpC is not None:
                return tmpC

        return None

    def getCoreModule(self, name):
        tmpW = self.coreWorkspace.getModuleByName(name)
        tmpC = self.core.getModuleByName(name)

        if tmpW is not None:
            return tmpW
        else:
            if tmpC is not None:
                return tmpC

        return None

    def getRequiredModules(self):
        tmp = []
        for x in self.validModuleTargets():
            tmp.append(x.module)

        self.requiredModules = list(set(tmp))

        return self.requiredModules

    def getRequiredPackages(self):
        tmp = []
        for x in self.validModuleTargets():
            for y in x.requiredPackages:
                tmp.append(y)

            m = self.getCoreModule(x.module)
            if m is not None:
                for y in m.requiredPackages:
                    tmp.append(y)

        for x in self.validParameterTargets():
            p = self.getParameters(x.parameters)
            if p is not None:
                for y in p.requiredPackages():
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
            tmpW = self.coreWorkspace.getPackageByName(x)
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
            tmpW = self.coreWorkspace.getPackageByName(x)
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
            tmpW = self.coreWorkspace.getModuleByName(x)
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
            tmpW = self.coreWorkspace.getModuleByName(x)
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

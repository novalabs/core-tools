# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from CorePackage import *
from CoreModule import *
from ModuleTarget import *

class CoreContainer:
    def __init__(self):
        self.invalidModules = []
        self.validModules = []
        self.validPackages = []
        self.invalidPackages = []
        self.validModuleTargets = []
        self.invalidModuleTargets = []

    def listPackages(self):
        path = self.getPackagesRoot()

        dirs = listDirectories(path, fullpath=True)

        tmp = []

        for x in dirs:
            if CorePackage.check(x):
                tmp.append(x)

        if tmp is not None:
            tmp.sort()

        return tmp

    def openPackages(self):
        list = self.listPackages()

        self.validPackages = []
        self.invalidPackages = []

        for x in list:
            p = CorePackage()
            if p.open(x):
                self.validPackages.append(p)
            else:
                self.invalidPackages.append(p)

        return self.validPackages

    def getPackageByName(self, name):
        if name is None:
            raise CoreError("CoreContainer::getPackageByName() name is None")

        for x in self.validPackages:
            if x.name == name:
                return x

        return None

    def listModules(self):
        path=self.getModulesRoot()

        dirs = listDirectories(path, fullpath=True)

        tmp = []

        for x in dirs:
            if CoreModule.check(x):
                tmp.append(x)

        if tmp is not None:
            tmp.sort()

        return tmp

    def openModules(self):
        list = self.listModules()

        self.validModules = []
        self.invalidModules = []

        for x in list:
            m = CoreModule()
            if m.open(x):
                self.validModules.append(m)
            else:
                self.invalidModules.append(m)

        return self.validModules

    def getModuleByName(self, name):
        if name is None:
            raise CoreError("CoreContainer::getModule() name is None")

        for x in self.validModules:
            if x.name == name:
                return x

        return None

    def listModuleTargets(self):
        path=self.getModuleTargetsRoot()

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

        self.validModuleTargets = []
        self.invalidModuleTargets = []

        for x in list:
            m = ModuleTarget()
            if m.open(x):
                self.validModuleTargets.append(m)
            else:
                self.invalidModuleTargets.append(m)

        return self.validModuleTargets
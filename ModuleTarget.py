# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from CoreUtils import *
from CoreModule import *


class ModuleTarget:
    schema = '{ "type": "record", "name": "ModuleTarget", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "module", "type": "string" }, { "name": "required_packages", "type": { "type": "array", "items": "string" } }, { "name": "sources", "type": { "type": "array", "items": "string" } }, { "name": "includes", "type": { "type": "array", "items": "string" } } ] }'

    def __init__(self):
        self.data = []
        self.workspace = None
        self.filename = ""
        self.source = ""
        self.name = ""
        self.namespace = ""
        self.description = ""
        self.destination = ""
        self.requiredPackages = ""
        self.module = ""
        self.sources = None
        self.includes = None
        self.valid = False
        self.reason = ""
        self.buffer = []
        self.coreModule = None
        self.moduleTargetRoot = None

    def openJSON(self, filename):
        CoreConsole.info("MODULE_TARGET: " + CoreConsole.highlightFilename(filename))

        try:
            self.data = loadAndValidateJson(filename, ModuleTarget.schema)
            if self.filename == self.data["name"]:
                self.source = filename
                self.name = self.data["name"]
                self.description = self.data["description"]
                self.module = self.data["module"]
                self.sources = []
                for x in self.data["sources"]:
                    self.sources.append(x)

                self.includes = []
                for x in self.data["includes"]:
                    self.includes.append(x)

                self.requiredPackages = []
                for x in self.data["required_packages"]:
                    self.requiredPackages.append(x)

                self.valid = True

                return True
            else:
                self.reason = "Target folder/name mismatch [" + self.filename + "/" + self.data["name"] + "]"
                CoreConsole.fail("ModuleTarget::openJSON: " + self.reason)
                self.valid = False

                return False

        except CoreError as e:
            self.reason = str(e.value)
            CoreConsole.fail("ModuleTarget::openJSON: " + self.reason)

            return False

    def getRoot(self):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("MODULE_TARGET.json")
            if self.root is not None:
                CoreConsole.ok("ModuleTarget::getRoot: ModuleTarget found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "ModuleTarget::getRoot: Not inside a ModuleTarget"
                CoreConsole.fail(self.reason)

        return self.root

    def open(self, root=None, name=None):
        self.valid = False

        if root is not None:
            if name is not None:
                self.moduleTargetRoot = os.path.join(root, name)
            else:
                self.moduleTargetRoot = root
        else:
            self.moduleTargetRoot = self.getRoot()

        if self.moduleTargetRoot is not None:
            (root, name) = os.path.split(self.moduleTargetRoot)
        else:
            return False

        self.root = root
        self.filename = name

        filename = os.path.join(self.moduleTargetRoot, "MODULE_TARGET.json")

        try:
            return self.openJSON(filename)
        except CoreError as e:
            CoreConsole.fail("ModuleTarget::open " + CoreConsole.highlightFilename(filename) + ": " + str(e.value))

        self.valid = False
        return False

    def generate(self, out=""):
        if self.valid:
            try:
                if out == "":
                    out = os.path.join(self.workspace, self.name)
                else:
                    if not os.path.isdir(out):
                        os.mkdir(out)

                self.destination = os.path.join(out, "CMakeLists.txt")
                sink = open(self.destination, 'w')

                self.process()

                sink.write("\n".join(self.buffer))
                CoreConsole.ok("ModuleTarget::generate " + CoreConsole.highlightFilename(self.destination))

                return True
            except IOError as e:
                self.reason = CoreConsole.error(str(e.strerror) + " [" + CoreConsole.highlightFilename(e.filename) + "]")
                CoreConsole.fail("ModuleTarget::generate: " + self.reason)

        return False

    def process(self):
        self.buffer = []
        if self.valid:
            self.__processPreamble()
            self.__processIncludes()
            self.__processSources()
            self.__processCoreTarget()

    def __processPreamble(self):
        self.buffer.append('# Generated by ModuleTarget.py')
        self.buffer.append('# Remove a "#" from the line below to stop generating this file every time you call CoreWorkspace generate')
        self.buffer.append('## TARGET MODULE ' + self.module)
        self.buffer.append('')
        self.buffer.append('PROJECT( ' + self.name + ' )')
        self.buffer.append('CMAKE_MINIMUM_REQUIRED(VERSION 2.8)')
        self.buffer.append('')
        self.buffer.append('FIND_PACKAGE( CORE_BUILD CONFIG REQUIRED )')
        self.buffer.append('')
        self.buffer.append('INCLUDE ( CoreTarget NO_POLICY_SCOPE )')

    def __processIncludes(self):
        self.buffer.append('SET( PROJECT_INCLUDE_DIRECTORIES')
        for x in self.includes:
            self.buffer.append('  ' + x)
        self.buffer.append(')')
        self.buffer.append('')

    def __processSources(self):
        self.buffer.append('SET( PROJECT_SOURCES')
        for x in self.sources:
            self.buffer.append('  ' + x)
        self.buffer.append(')')
        self.buffer.append('')

    def __processCoreTarget(self):
        self.buffer.append('core_target_module(')
        self.buffer.append('  MODULE ' + self.module)
        if len(self.requiredPackages) > 0:
            self.buffer.append('  PACKAGES')
            for x in self.requiredPackages:
                self.buffer.append('    ' + x)
        self.buffer.append(')')
        self.buffer.append('')

    @staticmethod
    def check(root, name=None):
        if name is None:
            return os.path.exists(os.path.join(root,"MODULE_TARGET.json"))
        else:
            return os.path.exists(os.path.join(root, name, "MODULE_TARGET.json"))
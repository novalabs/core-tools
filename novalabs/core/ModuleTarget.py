# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreUtils import *

class ModuleTarget:
    schema = {
      "definitions" : {
        "record:ModuleTarget" : {
          "type" : "object",
          "required" : [ "name", "description", "module", "required_packages", "sources", "includes" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "module" : {
              "type" : "string"
            },
            "os_version" : {
              "oneOf" : [ {
                "type" : "null"
              }, {
                "$ref" : "#/definitions/enum:OSVersion"
              } ]
            },
            "required_packages" : {
              "type" : "array",
              "items" : {
                "type" : "string"
              }
            },
            "sources" : {
              "type" : "array",
              "items" : {
                "type" : "string"
              }
            },
            "includes" : {
              "type" : "array",
              "items" : {
                "type" : "string"
              }
            }
          }
        },
        "enum:OSVersion" : {
          "enum" : [ "CHIBIOS_3", "CHIBIOS_16" ]
        }
      },
      "$ref" : "#/definitions/record:ModuleTarget"
    }

    DEFAULT_OS_VERSION = "CHIBIOS_3"

    def __init__(self):
        self.workspace = None

        self.targetName = ""
        self.root = None
        self.moduleTargetRoot = None
        self.source = ""

        self.data = None

        self.name = ""
        self.namespace = ""
        self.description = ""
        self.module = ""
        self.os_version = ""

        self.destination = ""

        self.buffer = []

        self.valid = False
        self.generated = False
        self.reason = ""

        self.sources = None
        self.includes = None
        self.requiredPackages = ""

        self.coreModule = None

    def openJSON(self, jsonFile):
        CoreConsole.info("MODULE_TARGET: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, ModuleTarget.schema)
            if self.targetName == self.data["name"]:
                self.source = jsonFile
                self.name = self.data["name"]
                self.description = self.data["description"]
                self.module = self.data["module"]

                if "os_version" in self.data:
                    self.os_version = self.data["os_version"]
                else:
                    self.os_version = self.DEFAULT_OS_VERSION

                self.sources = []
                for x in self.data["sources"]:
                    self.sources.append(x)

                self.includes = []
                for x in self.data["includes"]:
                    self.includes.append(x)

                self.requiredPackages = []
                for x in self.data["required_packages"]:
                    self.requiredPackages.append(x)

                CoreConsole.ok("ModuleTarget:: valid")

                self.valid = True

                return True
            else:
                raise CoreError("Target filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ModuleTarget::openJSON: " + self.reason)

        return False

    def getRoot(self, cwd = None):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("MODULE_TARGET.json", cwd)
            if self.root is not None:
                CoreConsole.ok("ModuleTarget::getRoot: ModuleTarget found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "ModuleTarget::getRoot: Not inside a ModuleTarget"
                CoreConsole.fail(self.reason)

        return self.root

    def open(self, root=None, name=None):
        self.__init__()

        CoreConsole.info("ModuleTarget::open(" + str(root) + ", " + str(name) + ")")

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
        self.targetName = name

        filename = os.path.join(self.moduleTargetRoot, "MODULE_TARGET.json")

        try:
            return self.openJSON(filename)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ParametersTarget::open " + self.reason)

        self.valid = False
        return False

    def generate(self, out="", skip=False):
        self.generated = False
        if self.valid:
            try:
                if out == "":
                    out = os.path.join(self.workspace, self.name)
                else:
                    if not os.path.isdir(out):
                        os.mkdir(out)

                self.destination = os.path.join(out, "CMakeLists.txt")

                if not skip:
                    sink = open(self.destination, 'w')

                    self.process()

                    sink.write("\n".join(self.buffer))
                    CoreConsole.ok("ModuleTarget::generate " + CoreConsole.highlightFilename(self.destination))
                else:
                    CoreConsole.ok("ModuleTarget::generate " + CoreConsole.highlightFilename(self.destination) + " SKIPPED")

                self.generated = True
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
        if self.os_version is not None:
            self.buffer.append('  OS_VERSION ' + self.os_version)
        if len(self.requiredPackages) > 0:
            self.buffer.append('  PACKAGES')
            for x in self.requiredPackages:
                self.buffer.append('    ' + x)
        self.buffer.append(')')
        self.buffer.append('')

    @staticmethod
    def check(root, name=None):
        if name is None:
            return os.path.exists(os.path.join(root, "MODULE_TARGET.json"))
        else:
            return os.path.exists(os.path.join(root, name, "MODULE_TARGET.json"))


    def getSummary(self, relpath=None):
        if relpath is not None:
            src = os.path.relpath(self.moduleTargetRoot, relpath)
        else:
            src = os.path.relpath(self.moduleTargetRoot, relpath)

        if self.valid:
            return [CoreConsole.highlight(self.name), self.description, self.module, self.os_version, src, CoreConsole.success("OK")]
        else:
            return ["", "", "", "", src, CoreConsole.error(self.reason)]


    @staticmethod
    def getSummaryFields():
        return ["Name", "Description", "Module", "OS Version", "Root", "Status"]


    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        if self.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.moduleTargetRoot, relpathSrc)
            else:
                src = os.path.relpath(self.moduleTargetRoot, relpathSrc)

            if relpathDst is not None:
                dst = os.path.relpath(self.destination, relpathDst)
            else:
                dst = self.destination

            if self.generated:
                return [CoreConsole.highlight(self.name), self.description, self.module, self.os_version, src, dst]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.module, self.os_version, src, CoreConsole.error(self.reason)]
        else:
            return ["", CoreConsole.error(self.reason), "", "", ""]


    @staticmethod
    def getSummaryFieldsGenerate():
        return ["Name", "Description", "Module", "OS Version", "Root", "Generate"]


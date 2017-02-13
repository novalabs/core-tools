# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreUtils import *


class CoreModule:
    schema = {
      "definitions" : {
        "record:CoreModule" : {
          "type" : "object",
          "required" : [ "name", "description", "chip", "required_packages", "chibios_components" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "chip" : {
              "type" : "string"
            },
            "required_packages" : {
              "type" : "array",
              "items" : {
                "type" : "string"
              }
            },
            "chibios_components" : {
              "type" : "array",
              "items" : {
                "type" : "string"
              }
            }
          }
        }
      },
      "$ref" : "#/definitions/record:CoreModule"
    }

    def __init__(self):
        self.filename = ""
        self.root = None
        self.moduleRoot = ""
        self.source = ""

        self.data = []

        self.name = ""
        self.description = ""
        self.chip = ""

        self.destination = ""

        self.buffer = []

        self.sources = []
        self.includes = []
        self.link = False

        self.cmake = ""
        self.cmakePathPrefix = None

        self.valid = False
        self.generated = False
        self.reason = ""

        self.requiredPackages = []
        self.chibiosComponents = []

    def openJSON(self, jsonFile):
        CoreConsole.info("CORE_MODULE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreModule.schema)
            if (self.filename == self.data["name"]):
                self.source = jsonFile
                self.name = self.data["name"]
                self.description = self.data["description"]
                self.chip = self.data["chip"]
                self.chibiosComponents = self.data["chibios_components"]
                self.requiredPackages = self.data["required_packages"]

                self.valid = True

                return True
            else:
                raise CoreError("Module filename/name mismatch")
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreModule::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def getRoot(self):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("CORE_MODULE.json")
            if self.root is not None:
                CoreConsole.ok("CoreModule::getRoot: Package found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "CoreModule::getRoot: Not inside a Module"
                CoreConsole.fail(self.reason)

        return self.root

    def open(self, root=None, name=None):
        self.__init__()

        if root is not None:
            if name is not None:
                self.moduleRoot = os.path.join(root, name)
            else:
                self.moduleRoot = root
        else:
            self.moduleRoot = self.getRoot()

        if self.moduleRoot is not None:
            (root, name) = os.path.split(self.moduleRoot)
        else:
            return False

        self.root = root
        self.filename = name

        jsonFile = os.path.join(self.moduleRoot, "CORE_MODULE.json")

        try:
            return self.openJSON(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreModule::open: " + self.reason)
            return False

    def generate(self, path, cmakePathPrefix=None, link = False):
        self.cmakePathPrefix = cmakePathPrefix
        self.generated = False
        self.link = link

        try:
            if (self.valid):
                if path is None:
                    raise CoreError("'out' file is empty")
                try:
                    path = os.path.join(path, self.name)

                    self.destination = path

                    self.process()

                    CoreConsole.ok("CoreModule::generate " + CoreConsole.highlightFilename(self.destination))

                    self.generated = True

                    return True
                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreModule::generate: " + self.reason)
            return False

    def process(self):
        srcIncludes = os.path.join(self.moduleRoot, "include")
        dstIncludes = os.path.join(self.destination, "include", self.name)

        if not os.path.isdir(self.destination):
            os.makedirs(self.destination    )

        self.includes = listFiles(srcIncludes)
        if len(self.includes) > 0:
            if not os.path.isdir(dstIncludes):
                os.makedirs(dstIncludes)
            for file in self.includes:
                copyOrLink(os.path.join(srcIncludes, file), os.path.join(dstIncludes, file), link=self.link)

        srcSources = os.path.join(self.moduleRoot, "src")
        dstSources = os.path.join(self.destination, "src")

        self.sources = listFiles(srcSources)
        if len(self.sources) > 0:
            if not os.path.isdir(dstSources):
                os.makedirs(dstSources)
            for file in self.sources:
                copyOrLink(os.path.join(srcSources, file), os.path.join(dstSources, file), link=self.link)

        srcMisc = os.path.join(self.moduleRoot, "misc")
        dstMisc = os.path.join(self.destination, "misc")

        misc = listFiles(srcMisc)
        if len(misc) > 0:
            if not os.path.isdir(dstMisc):
                os.makedirs(dstMisc)
            for file in misc:
                copyOrLink(os.path.join(srcMisc, file), os.path.join(dstMisc, file), link=self.link)

        self.__processCMake()

        self.cmake = os.path.join(self.destination, self.name + "Config.cmake")
        sink = open(self.cmake, 'w')

        sink.write("\n".join(self.buffer))

    def __processCMake(self):
        self.buffer = []
        self.buffer.append('LIST( APPEND WORKSPACE_MODULES_MODULES ' + self.name + ' )')

        self.buffer.append('SET( WORKSPACE_MODULES_' + self.name + '_REQUIRED_PACKAGES')
        for package in self.requiredPackages:
            self.buffer.append('  ' + package)
        self.buffer.append(')')

        self.buffer.append('SET( WORKSPACE_MODULES_' + self.name + '_CHIBIOS_REQUIRED_COMPONENTS')
        for component in self.chibiosComponents:
            self.buffer.append('  ' + component)
        self.buffer.append(')')

        if self.cmakePathPrefix is None:
            self.buffer.append('SET( WORKSPACE_MODULES_' + self.name + '_SOURCES')
            for src in self.sources:
                self.buffer.append('  ' + os.path.join(self.destination, "src", src))
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_MODULES_' + self.name + '_INCLUDES')
            self.buffer.append('  ' + os.path.join(self.destination, "include"))
            self.buffer.append('  ' + os.path.join(self.destination, "include", self.name))
            self.buffer.append(')')
        else:
            self.buffer.append('SET( WORKSPACE_MODULES_' + self.name + '_SOURCES')
            for src in self.sources:
                self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/src/" + src)
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_MODULES_' + self.name + '_INCLUDES')
            self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/include")
            self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/include/" + self.name)
            self.buffer.append(')')
        self.buffer.append('')

    def getSummary(self, relpath=None):
        table = []
        if self.valid:
            if relpath is not None:
                return [CoreConsole.highlight(self.name), self.description, self.chip, os.path.relpath(self.moduleRoot, relpath)]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.chip, self.moduleRoot]
        else:
            return ["", CoreConsole.error(self.reason), "", ""]

    @staticmethod
    def getSummaryFields():
        return ["Name", "Description", "Chip", "Root"]

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        table = []
        if self.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.moduleRoot, relpathSrc)
            else:
                src = self.moduleRoot

            if relpathDst is not None:
                dst = os.path.relpath(self.destination, relpathDst)
            else:
                dst = self.destination

            if self.link:
                dst = dst + CoreConsole.highlight(" [LINKS]")

            if self.generated:
                return [CoreConsole.highlight(self.name), self.description, self.chip, src, dst]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.chip, src, CoreConsole.error(self.reason)]
        else:
            return ["", CoreConsole.error(self.reason), "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["Name", "Description", "Chip", "Root", "Generate"]

    @staticmethod
    def check(root, name=None):
        if name is None:
            return os.path.exists(os.path.join(root, "CORE_MODULE.json"))
        else:
            return os.path.exists(os.path.join(root, name, "CORE_MODULE.json"))


# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreConsole import *
from .CoreConfiguration import *
from .CoreMessage import *


class CorePackage:
    schema = {
      "definitions" : {
        "record:CorePackage" : {
          "type" : "object",
          "required" : [ "name", "description", "provider" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "provider" : {
              "type" : "string"
            }
          }
        }
      },
      "$ref" : "#/definitions/record:CorePackage"
    }

    def __init__(self):
        self.filename = ""
        self.root = None
        self.packageRoot = ""
        self.source = ""

        self.data = None

        self.name = ""
        self.description = ""
        self.provider = ""

        self.destination = None
        self.docDestination = None

        self.buffer = []

        self.sources = []
        self.cmakeSources = []
        self.includes = []
        self.link = False

        self.cmake = ""
        self.cmakePathPrefix = None

        self.valid = False
        self.generated = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("CORE_PACKAGE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CorePackage.schema)

            if self.filename == self.data["name"]:
                self.source = jsonFile
                self.name = self.data["name"]
                self.description = self.data["description"]
                self.provider = self.data["provider"]

                self.valid = True
            else:
                raise CoreError("Package filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, root=None, name=None):
        self.__init__()

        if root is not None:
            if name is not None:
                self.packageRoot = os.path.join(root, name)
            else:
                self.packageRoot = root
        else:
            self.packageRoot = self.getRoot()

        if self.packageRoot is not None:
            (root, name) = os.path.split(self.packageRoot)
        else:
            return False

        self.root = root
        self.filename = name

        jsonFile = os.path.join(self.packageRoot, "CORE_PACKAGE.json")

        try:
            return self.openJSON(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::open: " + self.reason)
            return False

    def getRoot(self):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("CORE_PACKAGE.json")
            if self.root is not None:
                CoreConsole.ok("CorePackage::getRoot: Package found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "CorePackage::getRoot: Not inside a Package"
                CoreConsole.fail(self.reason)

        return self.root

    def generate(self, path, cmakePathPrefix=None, link=False):
        if not self.generatePackage(path, cmakePathPrefix, link):
            return False

        if not self.generateDocumentation(path):
            return False

        return True

    def generatePackage(self, path, cmakePathPrefix=None, link=False):
        self.cmakePathPrefix = cmakePathPrefix
        self.generated = False
        self.link = link

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    path = os.path.join(path, self.name)

                    self.destination = path

                    if not os.path.isdir(self.destination):
                        os.makedirs(self.destination)

                    self.process()

                    CoreConsole.ok("CorePackage::generate " + CoreConsole.highlightFilename(self.destination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::generate: " + self.reason)
            return False

        return True

    def generateDocumentation(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    path = os.path.join(path, self.name, "doc")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.name + ".adoc"))

                    self.processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CorePackage::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::generateDocumentation: " + self.reason)
            return False

        return True


    def process(self):
        srcIncludes = os.path.join(self.packageRoot, "include")
        dstIncludes = os.path.join(self.destination, "include", self.provider, self.name)

        self.includes = listFiles(srcIncludes)
        if len(self.includes) > 0:
            if not os.path.isdir(dstIncludes):
                os.makedirs(dstIncludes)
            for file in self.includes:
                copyOrLink(os.path.join(srcIncludes, file), os.path.join(dstIncludes, file), link=self.link)

        srcSources = os.path.join(self.packageRoot, "src")
        dstSources = os.path.join(self.destination, "src")

        self.sources = listFiles(srcSources)
        if len(self.sources) > 0:
            if not os.path.isdir(dstSources):
                os.makedirs(dstSources)
            for file in self.sources:
                copyOrLink(os.path.join(srcSources, file), os.path.join(dstSources, file), link=self.link)

        self.cmakeSources = listFiles(srcSources)

        for conf in self.listConfigurationFiles():
            self.cmakeSources.append(conf + ".cpp")  # TODO: now we assume that it will be generated...

        self.processCMake()

        self.cmake = os.path.join(self.destination, self.name + "Config.cmake")
        sink = open(self.cmake, 'w')

        sink.write("\n".join(self.buffer))

    def processCMake(self):
        self.buffer = []

        if self.cmakePathPrefix is None:
            self.buffer.append('LIST( APPEND WORKSPACE_PACKAGES_MODULES ' + self.name + ' )')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_SOURCES')
            for src in self.cmakeSources:
                self.buffer.append('  ' + os.path.join(self.destination, "src", src))
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_INCLUDES')
            self.buffer.append('  ' + os.path.join(self.destination, "include"))
            self.buffer.append(')')
            self.buffer.append('')
        else:
            self.buffer.append('LIST( APPEND WORKSPACE_PACKAGES_MODULES ' + self.name + ' )')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_SOURCES')
            for src in self.cmakeSources:
                self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/src/" + src)
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.name + '_INCLUDES')
            self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.name + "/include")
            self.buffer.append(')')
            self.buffer.append('')

    def __processDocumentationPreamble(self):
        t = """
[[anchor_pack-{provider}::{package}]]
== {provider}::{package}
_{description}_
"""
        s = SuperFormatter()
        self.buffer.append(s.format(t, package=self.name, provider=self.provider, description=self.description))

    def __processDocumentationEnd(self):
        tmp, dummy = os.path.splitext(self.source)
        addDocFile = os.path.join(self.packageRoot, self.name + ".adoc")

        if os.path.exists(addDocFile):
            with open(addDocFile, "r") as f:
                t = f.read()
                s = SuperFormatter()
                self.buffer.append(s.format(t, name=self.name, provider=self.provider, package=self.name, fqn=self.provider + "::" + self.name))

    def processDocumentation(self):
        self.buffer = []
        if self.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationEnd()

    def getSummary(self, relpath=None):
        if self.valid:
            if relpath is not None:
                return [CoreConsole.highlight(self.name), self.description, self.provider, os.path.relpath(self.packageRoot, relpath)]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.provider, self.packageRoot]
        else:
            return ["", CoreConsole.error(self.reason), ""]

    @staticmethod
    def getSummaryFields():
        return ["Name", "Description", "Provider", "Root"]

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        if self.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.packageRoot, relpathSrc)
            else:
                src = self.packageRoot

            if relpathDst is not None:
                dst = os.path.relpath(self.destination, relpathDst)
            else:
                dst = self.destination

            if self.link:
                dst = dst + CoreConsole.highlight(" [LINKS]")

            if self.generated:
                return [CoreConsole.highlight(self.name), self.description, self.provider, src, dst]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.provider, src, CoreConsole.error(self.reason)]
        else:
            return ["", CoreConsole.error(self.reason), "", "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["Name", "Description", "Provider", "Root", "Generate"]

    def listMessageFiles(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "messages")
        return listFilesByAndStripExtension(path, ".json")

    def listConfigurationFiles(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "configurations")
        files = listFilesByAndStripExtension(path, ".json")
        tmp = []
        for f in files:
            if not f.endswith(".default"): # Skip
                tmp.append(f)

        return tmp

    def listNodeFiles(self):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "nodes")
        return listFilesByAndStripExtension(path, ".json")

    def getMessageFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "messages", (x + ".json"))
        if os.path.isfile(path):
            return path
        else:
            raise CoreError("Message " + x + " not found in package")

    def getConfigurationFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "configurations", (x + ".json"))
        if os.path.isfile(path):
            return path
        else:
            raise CoreError("Configuration " + x + " not found in package")

    def getConfigurationDefaultFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "configurations", (x + ".default.json"))
        if os.path.isfile(path):
            return path
        else:
            return None

    def getNodeFile(self, x):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        path = os.path.join(self.packageRoot, "nodes", (x + ".json"))
        if os.path.isfile(path):
            return path
        else:
            raise CoreError("Node " + x + " not found in package")

    def getIncludeDir(self, namespace=""):
        if not self.valid:
            raise CoreError("CorePackage::* invalid")
        if namespace == "":
            namespace = self.name
        return os.path.join(self.packageRoot, "include", namespace)

    @staticmethod
    def check(root, name=None):
        if name is None:
            return os.path.exists(os.path.join(root, "CORE_PACKAGE.json"))
        else:
            return os.path.exists(os.path.join(root, name, "CORE_PACKAGE.json"))


# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreWorkspace import *
from .CoreUtils import *
from intelhex import IntelHex
import struct

class Parameters:
    schema = {
      "definitions" : {
        "record:Parameters" : {
          "type" : "object",
          "required" : [ "name", "description", "objects" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "objects" : {
              "type" : "array",
              "items" : {
                "$ref" : "#/definitions/record:ObjectParameters"
              }
            }
          }
        },
        "record:ObjectParameters" : {
          "type" : "object",
          "required" : [ "object", "package", "parameters" ],
          "additionalProperties" : False,
          "properties" : {
            "object" : {
              "type" : "string"
            },
            "package" : {
              "type" : "string"
            },
            "parameters" : {
              "type" : "string"
            }
          }
        }
      },
      "$ref" : "#/definitions/record:Parameters"
    }

    def __init__(self):
        self.parametersRoot = ""
        self.source = ""
        self.root = ""
        self.parametersName = ""
        self.description = ""

        self.data = None
        self.objects = None

        self.valid = False
        self.generated = False
        self.reason = ""
        self.generatedBinary = None

        self._requiredPackages = []

    @staticmethod
    def check(root, name=None):
        if name is None:
            return os.path.exists(os.path.join(root, "PARAMETERS.json"))
        else:
            return os.path.exists(os.path.join(root, name, "PARAMETERS.json"))

    def openJSON(self, jsonFile: str):
        CoreConsole.info("PARAMETERS: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, Parameters.schema)
            if self.parametersName == self.data["name"]:
                self.source = jsonFile
                self.name = self.data["name"]
                self.description = self.data["description"]
                self.objects = self.data["objects"]

                self._requiredPackages = []
                for obj in self.objects:
                    self._requiredPackages.append(obj["package"])

                CoreConsole.ok("Parameters:: valid")

                self.valid = True

                return True
            else:
                raise CoreError("Parameters filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e.value)
            CoreConsole.fail("Parameters::openJSON: " + self.reason)

        return False

    def open(self, root, name=None):
        self.__init__()

        CoreConsole.info("ParametersTarget::open(" + str(name) + ", " + str(name) + ")")

        try:
            if root is not None:
                if name is None:
                    self.parametersRoot = root
                else:
                    self.parametersRoot = os.path.join(root, name)
            else:
                raise CoreError("Invalid Parameter root")

            if self.parametersRoot is not None:
                (root, name) = os.path.split(self.parametersRoot)
            else:
                raise CoreError("Invalid Parameter Target root")

            self.root = root
            self.parametersName = name

            filename = os.path.join(self.parametersRoot, "PARAMETERS.json")

            return self.openJSON(filename)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ParametersTarget::open " + self.reason)

        return False

    def requiredPackages(self):
        return self._requiredPackages


    def generateSchema(self, out="", skip=False):
        self.generated = False
        if self.valid:
            try:
                CoreConsole.info("Parameters::generateSchema TODO")

                self.generated = True

                return self.generated
            except IOError as e:
                self.reason = CoreConsole.error(str(e.strerror) + " [" + CoreConsole.highlightFilename(e.filename) + "]")
                CoreConsole.fail("Parameters::generateSchema: " + self.reason)

        return False

    def generateBinary(self, workspace, parametersTarget, out=""):
        self.generated = False
        self.generatedBinary = None

        if self.valid:
            try:
                CoreConsole.info("Parameters::generateBinary")

                buffer = bytearray()

                buffer.extend(struct.pack('<L', len(self.objects)))

                for obj in self.objects:
                    p = workspace.getCoreConfiguration(obj["package"], obj["parameters"])
                    bin, size = p.pack(parametersTarget.getObject(obj['object']), obj["object"])

                    if bin is None:
                        self.reason = obj['object'] + ": " +  p.reason
                        return False

                    buffer.extend(bin)

                CoreConsole.info(parametersTarget.name + " [" + self.name + "] generateBinary: " + repr(buffer))

                self.generatedBinary = buffer

                self.generated = True

                return self.generated
            except IOError as e:
                self.reason = CoreConsole.error(str(e.strerror) + " [" + CoreConsole.highlightFilename(e.filename) + "]")
                CoreConsole.fail("Parameters::generateBinary: " + self.reason)

        return False

    def getSummary(self, relpath=None):
        if relpath is not None:
            src = os.path.relpath(self.parametersRoot, relpath)
        else:
            src = self.parametersRoot

        if self.valid:
            return [CoreConsole.highlight(self.parametersName), self.description, src]
        else:
            return ["", CoreConsole.error(self.reason), src]


    @staticmethod
    def getSummaryFields():
        return ["Name", "Description", "Root"]

class ParametersTarget:
    schema = {
      "definitions" : {
        "record:ParametersTarget" : {
          "type" : "object",
          "required" : [ "name", "description", "target" ],
          "additionalProperties" : True,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "target" : {
              "type" : "string"
            }
          }
        }
      },
      "$ref" : "#/definitions/record:ParametersTarget"
    }

    def __init__(self):
        try:
            self.filename = ""
            self.root = None
            self.parameterTargetPath = None
            self.source = ""

            self.data = None

            self.name = ""
            self.parameters = ""
            self.description = ""

            self.destinationBin = None
            self.destinationHex = None

            self.generatedBinary = None

            self.valid = False
            self.generated = False
            self.reason = ""

            self.sources = None
            self.includes = None
            self.requiredPackages = ""

            self.coreModule = None

        except CoreError as e:
            self.reason = str(e.value)
            CoreConsole.fail("ParametersTarget::__init__: " + self.reason)

    def openJSON(self, jsonFile):
        CoreConsole.info("PARAMETERS_TARGET: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, ParametersTarget.schema)
            if self.name == self.data["name"] and self.parameters == self.data["target"]:
                self.source = jsonFile
                self.description = self.data["description"]

                CoreConsole.ok("ParametersTarget:: valid - fields will be tested later")

                self.valid = True

                return True
            else:
                raise CoreError("Target filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ParametersTarget::openJSON: " + self.reason)

        return False

    def open(self, root, name=None):
        self.__init__()

        CoreConsole.info("ParametersTarget::open(" + str(root) + ", " + str(name) + ")")

        try:
            if root is not None:
                if name is None:
                    self.parameterTargetPath = root
                else:
                    self.parameterTargetPath = os.path.join(root, name)
            else:
                raise CoreError("Invalid Parameter root")

            if self.parameterTargetPath is not None:
                (tmp, name) = os.path.split(self.parameterTargetPath)
                (root, target) = os.path.split(tmp)
            else:
                raise CoreError("Invalid Parameter Target root")

            self.root = root
            self.parameters = target
            self.name = name

            return self.openJSON(self.parameterTargetPath + ".json")
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ParametersTarget::open " + self.reason)

        return False

    def generate(self, workspace, outBin=None, outHex=None,skip=False):
        self.generated = False
        self.generatedBinary = None
        if self.valid:
            try:
                p = workspace.getParameters(self.parameters)

                if p is not None:
                    if p.generateBinary(workspace, self):
                        if outBin is not None:
                            path = os.path.join(outBin, self.parameters)
                            if not os.path.isdir(path):
                                os.makedirs(path)

                            self.destinationBin = os.path.join(path, self.name + ".bin")

                            sink = open(self.destinationBin, 'wb')
                            sink.write(p.generatedBinary)
                        else:
                            self.destinationBin = None

                        if outHex is not None:
                            path = os.path.join(outHex, self.parameters)
                            if not os.path.isdir(path):
                                os.makedirs(path)

                            self.destinationHex = os.path.join(path, self.name + ".hex")

                            ih = IntelHex()
                            ih.frombytes(p.generatedBinary)
                            ih.tofile(self.destinationHex, "hex")
                        else:
                            self.destinationHex = None

                        self.generated = True
                    else:
                        self.reason = p.reason
                else:
                    self.reason = "Cannot find a valid parameters file for '" + self.parameters + "'"

                return self.generated
            except IOError as e:
                self.reason = CoreConsole.error(str(e.strerror) + " [" + CoreConsole.highlightFilename(e.filename) + "]")
                CoreConsole.fail("ParametersTarget::generate: " + self.reason)

        return False


    def getObject(self, name):
        if name in self.data['parameters']:
            return self.data['parameters'][name]
        else:
            return []

    def getSummary(self, relpath=None):
        if relpath is not None:
            src = os.path.relpath(self.root, relpath)
        else:
            src = self.root

        if self.valid:
            return [CoreConsole.highlight(self.name), self.description, self.parameters, src, CoreConsole.success("OK")]
        else:
            return ["", "",  self.parameters, src, CoreConsole.error(self.reason)]

    @staticmethod
    def getSummaryFields():
        return ["Name", "Description", "Parameters", "Root", "Status"]

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        if self.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.source, relpathSrc)
            else:
                src = self.source

            if relpathDst is not None:
                if self.destinationBin is not None:
                    dstBin = os.path.relpath(self.destinationBin, relpathDst)
                else:
                    dstBin = None
                if self.destinationHex is not None:
                    dstHex = os.path.relpath(self.destinationHex, relpathDst)
                else:
                    dstHex = None
            else:
                dstBin = self.destinationBin
                dstHex = self.destinationHex

            if self.generated:
                return [CoreConsole.highlight(self.name), self.description, self.parameters, src, str(dstBin), str(dstHex), CoreConsole.success("OK")]
            else:
                return [CoreConsole.highlight(self.name), self.description, self.parameters, src, str(dstBin), str(dstHex), CoreConsole.error(self.reason)]
        else:
            return ["", "", "", "", "", "", CoreConsole.error(self.reason)]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["Name", "Description", "Parameters", "Source", "Generated Bin", "Generated Hex", "Status"]

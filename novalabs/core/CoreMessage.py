# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import zlib

from .CoreUtils import *


class CoreMessage:
    schema = {
      "definitions" : {
        "record:CoreMessage" : {
          "type" : "object",
          "required" : [ "name", "description", "namespace", "fields" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "namespace" : {
              "type" : "string"
            },
            "fields" : {
              "type" : "array",
              "items" : {
                "$ref" : "#/definitions/record:CoreConfigurationParameter"
              }
            }
          }
        },
        "record:CoreConfigurationParameter" : {
          "type" : "object",
          "required" : [ "name", "description", "type", "size" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            },
            "type" : {
              "$ref" : "#/definitions/enum:CoreConfigurationParameterDataType"
            },
            "size" : {
              "default" : 1,
              "type" : "integer",
              "minimum" : -2147483648,
              "maximum" : 2147483647
            }
          }
        },
        "enum:CoreConfigurationParameterDataType" : {
          "enum" : [ "CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64", "TIMESTAMP" ]
        }
      },
      "$ref" : "#/definitions/record:CoreMessage"
    }

    fieldtypeOrder = ["TIMESTAMP", "INT64", "UINT64", "FLOAT64", "INT32", "UINT32", "FLOAT32", "INT16", "UINT16", "CHAR", "INT8", "UINT8"]

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None

        self.name = ""
        self.namespace = ""
        self.description = ""

        self.hppDestination = ""
        self.docDestination = ""

        self.orderedFields = []
        self.buffer = []

        self.signature = 0xffffffff
        self.signatureBuffer = []

        self.valid = False
        self.generated = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("MESSAGE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreMessage.schema)
            if self.filename == self.data["name"]:
                self.source = jsonFile
                self.name = self.data["name"]
                self.namespace = self.data["namespace"]
                self.description = self.data["description"]
                if self.namespace == "@" or self.namespace == "":
                    if self.package is not None:
                        self.namespace = self.package.name

                if self.package is not None:
                    self.namespace = self.package.provider + "::" + self.namespace

                self.valid = True
            else:
                raise CoreError("Message filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, name, package=None):
        self.__init__()

        if package is not None:
            jsonFile = package.getMessageFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            self.openJSON(jsonFile)

            self.valid = self.preProcess()  # sort the fields

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::open: " + self.reason)
            return False

    def generateHeader(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "include", self.package.provider, self.package.name)
                    else:
                        path = path

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.hppDestination = os.path.join(path, (self.name + ".hpp"))

                    self.process()

                    sink = open(self.hppDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreMessage::generate " + CoreConsole.highlightFilename(self.hppDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::generate: " + self.reason)
            return False

        return True

    def generateDocumentation(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "doc", "msgs")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.name + ".adoc"))

                    self.processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreMessage::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::generateDocumentation: " + self.reason)
            return False

        return True

    def generate(self, path):
        if not self.generateHeader(path):
            return False

        if not self.generateDocumentation(path):
            return False

        return True

    def preProcess(self):
        try:
            if self.valid:
                self.signatureBuffer = []
                self.orderedFields = []

                fields = self.data['fields']
                for fieldType in self.fieldtypeOrder:
                    for field in fields:
                        if fieldType == field['type']:
                            self.orderedFields.append(field)
                            self.signatureBuffer.append(field['name'])
                            self.signatureBuffer.append(field['type'])
                            self.signatureBuffer.append(str(field['size']))

                            if not 'notes' in field:
                                field['notes'] = None

                self.__updateSignature()
                return True
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::preProcess: " + self.reason)
            return False

    def __updateSignature(self):
        self.signature = (zlib.crc32(bytearray(':'.join(self.signatureBuffer), 'ascii')) & 0xffffffff)

    def process(self):
        self.buffer = []
        if self.valid:
            self.__processPreamble()
            self.__processNamsepaceBegin()
            self.__processMessageBegin()
            self.__processFields()
            self.__processMessageSignature()
            self.__processMessageEnd()
            self.__processNamsepaceEnd()

    def __processPreamble(self):
        self.buffer.append('#pragma once')
        self.buffer.append('')
        self.buffer.append('#include <core/mw/CoreMessage.hpp>')
        self.buffer.append('')

    def __processNamsepaceBegin(self):
        namespace = self.namespace
        for ns in namespace.split('::'):
            self.buffer.append('namespace ' + ns + ' {')
        self.buffer.append('')

    def __processMessageBegin(self):
        self.buffer.append('CORE_MESSAGE_BEGIN(' + self.data['name'] + ') //' + self.data['description'])

    def __processFields(self):
        fields = self.orderedFields
        for field in fields:
            self.buffer.append('	CORE_MESSAGE_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'])

    def __processMessageSignature(self):
        self.buffer.append('CORE_MESSAGE_SIGNATURE(' + hex(self.signature) + ')')

    def __processMessageEnd(self):
        self.buffer.append('CORE_MESSAGE_END')

    def __processNamsepaceEnd(self):
        namespace = self.namespace
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')

    def __processDocumentationPreamble(self):
        t = """
[[anchor_msg-{namespace}::{data[name]}]]
=== {namespace}::{data[name]}
_{data[description]}_
"""
        s = SuperFormatter()
        self.buffer.append(s.format(t, namespace=self.namespace, data=self.data))

    def __processDocumentationEnd(self):
        tmp, dummy = os.path.splitext(self.source)
        addDocFile = tmp + ".adoc"

        if os.path.exists(addDocFile):
            with open(addDocFile, "r") as f:
                t = f.read()
                s = SuperFormatter()
                self.buffer.append(s.format(t, namespace=self.namespace, name=self.data['name'], provider=self.package.provider, package=self.package.name, fqn=self.namespace + "::" + self.data['name']))

    def __processDocumentationFields(self):
        t_begin = """
[cols="20,62,10,8", options="header"]
.{namespace}::{data[name]}
|===

| Field | Description | Type | Size
        """
        t_field = """.2+^.^| `{field[name]}` | {field[description]} | `{field[type]}` | {field[size]}
    3+| {emit_notes:if:+
_{field[notes]}_}"""

        t_end = """
|===
"""
        s = SuperFormatter()

        self.buffer.append(s.format(t_begin, namespace=self.namespace, data=self.data))

        for field in self.data['fields']:
            self.buffer.append(s.format(t_field, field=field, emit_notes=field['notes'] is not None))

        self.buffer.append(s.format(t_end, namespace=self.namespace, data=self.data, json=self.source))

    def processDocumentation(self):
        self.buffer = []
        if self.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationFields()
            self.__processDocumentationEnd()

    def getSummary(self, relpath=None):
        if self.valid:
            if relpath is not None:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, os.path.relpath(self.source, relpath)]
            else:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, self.source]
        else:
            return ["", "", CoreConsole.error(self.reason), ""]

    @staticmethod
    def getSummaryFields():
        return ["NS", "Name", "Description", "Source"]

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        if self.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.source, relpathSrc)
            else:
                src = self.source

            if relpathDst is not None:
                hppDst = os.path.relpath(self.hppDestination, relpathDst)
                docDst = os.path.relpath(self.docDestination, relpathDst)
            else:
                hppDst = self.hppDestination
                docDst = self.docDestination

            if self.generated:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, hppDst, docDst]
            else:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, CoreConsole.error(self.reason), ""]
        else:
            return ["", "", CoreConsole.error(self.reason), "", "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generated hpp", "Generated doc"]

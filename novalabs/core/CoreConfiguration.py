# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import zlib
import struct

from .CoreUtils import *


class CoreConfiguration:
    schema = {
      "definitions" : {
        "record:CoreConfiguration" : {
          "type" : "object",
          "required" : [ "name", "description", "namespace", "fields" ],
          "additionalProperties" : True,
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
          "additionalProperties" : True,
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
          "enum" : [ "CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64" ]
        }
      },
      "$ref" : "#/definitions/record:CoreConfiguration"
    }

    FieldtypeOrder = ["TIMESTAMP", "INT64", "UINT64", "FLOAT64", "INT32", "UINT32", "FLOAT32", "INT16", "UINT16", "CHAR", "INT8", "UINT8"]

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None
        self.defaultData = None

        self.namespace = ""
        self.description = ""

        self.hppDestination = ""
        self.cppDestination = ""
        self.docDestination = ""

        self.orderedFields = []
        self.buffer = []

        self.signature = 0xffffffff
        self.signatureBuffer = []

        self.valid = False
        self.generated = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("CONFIGURATION: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreConfiguration.schema)
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

                if self.valid:
                    CoreConsole.ok("CoreConfiguration:: valid")

                return self.valid
            else:
                raise CoreError("Configuration filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::openJSON: " + self.reason)
            self.valid = False
            return False

    def openDefaultJSON(self, jsonFile):
        CoreConsole.info("CONFIGURATION DEFAULT: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.defaultData = loadJson(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::openDefaultJSON: " + self.reason)
            return False

    def open(self, name, package=None, defaultFile=None):
        self.__init__()

        if package is not None:
            jsonFile = package.getConfigurationFile(name)
            defaultFile = package.getConfigurationDefaultFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            if self.openJSON(jsonFile):
                if defaultFile is not None:
                    self.openDefaultJSON(defaultFile)
            self.valid = self.preProcess()  # sort the fields and calculate the signature

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::open: " + self.reason)
            return False

    def generate(self, path):
        if not self.generateHeader(path):
            return False

        if not self.generateSource(path):
            return False

        if not self.generateDocumentation(path):
            return False

        for field in self.data['fields']:
            if len(field['name']) > 23:
                self.reason = "Field name " + field['name'] + " is too long"
                self.generated = False
                return False

        return True

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
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.hppDestination = os.path.join(path, (self.name + ".hpp"))

                    self.processHeader()

                    sink = open(self.hppDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateHeader " + CoreConsole.highlightFilename(self.hppDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generate: " + self.reason)
            return False

        return True

    def generateSource(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "src")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.cppDestination = os.path.join(path, (self.name + ".cpp"))

                    self.processSource()

                    sink = open(self.cppDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateSource " + CoreConsole.highlightFilename(self.cppDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generate: " + self.reason)
            return False

        return True

    def preProcess(self):
        try:
            if self.valid:
                self.signatureBuffer = []
                self.orderedFields = []

                namespace = self.namespace
                for ns in namespace.split('::'):
                    self.signatureBuffer.append(ns)

                self.signatureBuffer.append(self.data['name'])

                fields = self.data['fields']
                for fieldType in self.FieldtypeOrder:
                    for field in fields:
                        if fieldType == field['type']:
                            self.orderedFields.append(field)
                            self.signatureBuffer.append(field['name'])
                            self.signatureBuffer.append(field['type'])
                            self.signatureBuffer.append(str(field['size']))

                            field['default'] = None

                            if not 'notes' in field:
                                field['notes'] = None

                            if self.defaultData is not None:
                                if field['name'] in self.defaultData:
                                    if checkCTypeValueForCoreType(field['type'], field['size'], self.defaultData[field['name']]) is not None:
                                        field['default'] = self.defaultData[field['name']]
                                    else:
                                        raise CoreError("Default value specified for field '" + field['name'] + "' is not compatible with CoreType<" + field['type'] + ", " + str(field['size']) + ">")

                self.__updateSignature()
                return True
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::preProcess: " + self.reason)
            return False

    def processHeader(self):
        self.buffer = []
        if self.valid:
            self.__processHeaderPreamble()

            self.__processNamsepaceBegin()

            self.__processConfigurationBegin()

            self.buffer.append("// --- FIELDS -----------------------------------------------------------------")
            self.__processFields()
            self.buffer.append("// ----------------------------------------------------------------------------")

            self.__processConfigurationSignature()
            self.__processConfigurationLength()

            self.__processConfigurationEnd()

            self.__processNamsepaceEnd()

    def processSource(self):
        self.buffer = []
        if self.valid:
            self.__processSourcePreamble()

            self.__processNamsepaceBegin()

            self.__processDefaultBegin()
            self.__processDefaultFields()
            self.__processDefaultEnd()

            self.__processConstructor()

            self.__processMapBegin()
            self.__processMapFields()
            self.__processMapEnd()

            self.__processNamsepaceEnd()

    def __processHeaderPreamble(self):
        self.buffer.append('#pragma once')
        self.buffer.append('')
        self.buffer.append('#include <core/mw/CoreConfiguration.hpp>')
        self.buffer.append('')

    def __processSourcePreamble(self):
        self.buffer.append('#include <' + os.path.join(self.package.provider, self.package.name, self.name + '.hpp') + '>')
        self.buffer.append('')

    def __processNamsepaceBegin(self):
        namespace = self.namespace
        for ns in namespace.split('::'):
            self.buffer.append('namespace ' + ns + ' {')
        self.buffer.append('')

    def __processConfigurationBegin(self):
        self.buffer.append('CORE_CONFIGURATION_BEGIN(' + self.data['name'] + ') //' + self.data['description'])

    def __updateSignature(self):
        self.signature = (zlib.crc32(bytearray(':'.join(self.signatureBuffer), 'ascii')) & 0xffffffff)

    def __processFields(self):
        fields = self.orderedFields
        for field in fields:
            self.buffer.append('	CORE_CONFIGURATION_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'] + ' [' + (str(field['default']) if field['default'] is not None else '') + ']')

    def __processConstructor(self):
        self.buffer.append('CORE_CONFIGURATION_CONSTRUCTOR_BEGIN(' + self.data['name'] + ')')

        buffer = ""
        fields = self.orderedFields
        for field in fields:
            if field['default'] is not None:
                buffer = buffer + '	CORE_CONFIGURATION_CONSTRUCTOR_FIELD(' + field['name'] + '), ' + "\n"
            else:
                buffer = buffer + '	CORE_CONFIGURATION_CONSTRUCTOR_FIELD_NONE(' + field['name'] + '), ' + "\n"
        buffer = buffer[:-3]

        self.buffer.append(buffer)

        self.buffer.append('CORE_CONFIGURATION_CONSTRUCTOR_END()')
        self.buffer.append('')

    def __processDefaultBegin(self):
        self.buffer.append('CORE_CONFIGURATION_DEFAULT_BEGIN()')

    def __processDefaultFields(self):
        fields = self.orderedFields
        for field in fields:
            if field['default'] is not None:
                self.buffer.append('	CORE_CONFIGURATION_DEFAULT_FIELD(' + field['name'] + ', ' + field['type'] + ', ' +  str(field['size']) + ', ' + formatValuesAsC(field['type'], field['size'], field['default']) + ')')

    def __processDefaultEnd(self):
        self.buffer.append('CORE_CONFIGURATION_DEFAULT_END()')
        self.buffer.append('')

    def __processMapBegin(self):
        name = self.data['name']
        self.buffer.append('CORE_CONFIGURATION_MAP_BEGIN(' + name + ')')

    def __processMapFields(self):
        fields = self.data['fields']
        for field in fields:
            self.buffer.append('	CORE_CONFIGURATION_MAP_ENTRY(' + self.data['name'] + ', ' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ')')

    def __processMapEnd(self):
        self.buffer.append('CORE_CONFIGURATION_MAP_END()')

    def __processConfigurationSignature(self):
        self.buffer.append('CORE_CONFIGURATION_SIGNATURE(' + hex(self.signature) + ')')

    def __processConfigurationLength(self):
        fields = self.data['fields']
        self.buffer.append('CORE_CONFIGURATION_LENGTH(' + str(len(fields)) + ')')

    def __processConfigurationEnd(self):
        self.buffer.append('CORE_CONFIGURATION_END()')

    def __processNamsepaceEnd(self):
        namespace = self.namespace
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')
        self.buffer.append('')

    def __processDocumentationPreamble(self):
        t = """
[[anchor_params-{namespace}::{data[name]}]]
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
    3+| {emit_default:if:Default: `{field[default]}`} {emit_notes:if:+
_{field[notes]}_}"""

        t_end = """
|===
"""
        s = SuperFormatter()

        self.buffer.append(s.format(t_begin, namespace=self.namespace, data=self.data))

        for field in self.data['fields']:
            self.buffer.append(s.format(t_field, field=field, emit_notes=field['notes'] is not None,  emit_default=field['default'] is not None))

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
                cppDst = os.path.relpath(self.cppDestination, relpathDst)
                docDst = os.path.relpath(self.docDestination, relpathDst)
            else:
                hppDst = self.hppDestination
                cppDst = self.cppDestination
                docDst = self.docDestination

            if self.generated:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, hppDst, cppDst, docDst]
            else:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, CoreConsole.error(self.reason), "", ""]
        else:
            return ["", "", CoreConsole.error(self.reason), "", "", "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generated hpp", "Generated cpp", "Generated doc"]

    def pack(self, fields, name=None):
        values = []
        if name is not None:
            formatString = '<16sL'
            values.append(bytes(name, "ascii"))
        else:
            formatString = '<L'

        values.append(self.signature)

        for field in self.orderedFields:

            if field['type'] == 'CHAR' and field['size'] > 1:
                formatString = formatString + '%ds' % field['size']
            else:
                formatString = formatString + field['size'] * TypeFormatMap[field['type']]

            value = None

            if field['name'] in fields:
                value = fields[field['name']]
            else:
                if field['default'] is not None:
                    value = field['default']

            if value is None:
                self.reason = "No value or default specified for field '" + field['name'] + "'"
                CoreConsole.fail("CoreConfiguration::pack: " + self.reason)
                return (None, 0)

            value = checkCTypeValueForCoreType(field['type'], field['size'], value)

            if value is None:
                self.reason = "Value specified for field '" + field['name'] + "' is not compatible with type '" + field['type'] + "[" + str(field['size']) + "]'"
                CoreConsole.fail("CoreConfiguration::pack: " + self.reason)
                return (None, 0)

            values = values + value

        s = struct.Struct(formatString)
        packed = s.pack(*values)

        CoreConsole.info("CoreConfiguration::pack: '" + formatString + "' [size=" + str(s.size) + "] " + repr(values) + " -> " + repr(packed))

        return (packed, s.size)

    def document(self):
        pass

    def generateDocumentation(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "doc", "params")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.name + ".adoc"))

                    self.processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generateDocumentation: " + self.reason)
            return False

        return True
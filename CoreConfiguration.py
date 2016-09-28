# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from CoreUtils import *
import zlib


class CoreConfiguration:
    schema = '{ "type": "record", "name": "CoreConfiguration", "namespace" : "", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "namespace", "type": "string" }, { "name": "fields", "type": { "type": "array", "items": { "type": "record", "name": "CoreConfigurationParameter", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "type", "type": { "type": "enum", "name": "CoreConfigurationParameterDataType", "symbols": [ "CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64" ] } }, { "name": "size", "type": "int", "default": 1 } ] } } } ] }'

    fieldtypeOrder = ["TIMESTAMP", "INT64", "UINT64", "FLOAT64", "INT32", "UINT32", "FLOAT32", "INT16", "UINT16", "CHAR", "INT8", "UINT8"]

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None

        self.name = ""
        self.namespace = ""
        self.description = ""

        self.destination = ""

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
            else:
                raise CoreError("Configuration filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, name, package=None):
        if package is not None:
            jsonFile = package.getConfigurationFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            return self.openJSON(jsonFile)

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::open: " + self.reason)
            return False

    def generate(self, path):
        if not self.generateHeader(path):
            return False

        if not self.generateSource(path):
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

                    self.destination = os.path.join(path, (self.name + ".hpp"))

                    self.processHeader()

                    sink = open(self.destination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateHeader " + CoreConsole.highlightFilename(self.destination))

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

                    self.destination = os.path.join(path, (self.name + ".cpp"))

                    self.processSource()

                    sink = open(self.destination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateSource " + CoreConsole.highlightFilename(self.destination))

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

    def processHeader(self):
        self.buffer = []
        self.signatureBuffer = []
        if self.valid:
            self.__processHeaderPreamble()

            self.__processNamsepaceBegin()

            self.__processConfigurationBegin()

            self.buffer.append("// --- FIELDS -----------------------------------------------------------------")
            self.__processFields()
            self.buffer.append("// ----------------------------------------------------------------------------")

            self.__updateSignature()

            self.__processConfigurationSignature()
            self.__processConfigurationLength()

            self.__processConfigurationEnd()

            self.__processNamsepaceEnd()

    def processSource(self):
        self.buffer = []
        if self.valid:
            self.__processSourcePreamble()

            self.__processNamsepaceBegin()

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
            self.signatureBuffer.append(ns)
        self.buffer.append('')

    def __processConfigurationBegin(self):
        self.buffer.append('CORE_CONFIGURATION_BEGIN(' + self.data['name'] + ') //' + self.data['description'])
        self.signatureBuffer.append(self.data['name'])

    def __updateSignature(self):
        self.signature = hex(zlib.crc32(b':'.join(self.signatureBuffer)) & 0xffffffff)

    def __processFields(self):
        fields = self.data['fields']
        for fieldType in self.fieldtypeOrder:
            for field in fields:
                if fieldType == field['type']:
                    self.buffer.append('	CORE_CONFIGURATION_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'])
                    self.signatureBuffer.append(field['name'])
                    self.signatureBuffer.append(field['type'])
                    self.signatureBuffer.append(str(field['size']))

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
        self.buffer.append('CORE_CONFIGURATION_SIGNATURE(' + str(self.signature) + ')')

    def __processConfigurationLength(self):
        fields = self.data['fields']
        self.buffer.append('CORE_CONFIGURATION_LENGTH(' + str(len(fields))  + ')')

    def __processConfigurationEnd(self):
        self.buffer.append('CORE_CONFIGURATION_END()')

    def __processNamsepaceEnd(self):
        namespace = self.namespace
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')
        self.buffer.append('')

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
                dst = os.path.relpath(self.destination, relpathDst)
            else:
                dst = self.destination

            if self.generated:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, dst]
            else:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, CoreConsole.error(self.reason)]
        else:
            return ["", "", CoreConsole.error(self.reason), "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generate"]

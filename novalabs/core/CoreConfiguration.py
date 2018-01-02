# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import zlib
import struct

from .CoreUtils import *
from .CoreTypes import *


class CoreConfiguration:
    SCHEMA = {
        "definitions": {
            "record:CoreConfiguration": {
                "type": "object",
                "required": ["name", "description", "namespace", "fields"],
                "additionalProperties": True,
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "namespace": {
                        "type": "string"
                    },
                    "fields": {
                        "type": "array",
                        "items": {
                            "$ref": "#/definitions/record:CoreConfigurationParameter"
                        }
                    }
                }
            },
            "record:CoreConfigurationParameter": {
                "type": "object",
                "required": ["name", "description", "type", "size"],
                "additionalProperties": True,
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "type": {
                        "$ref": "#/definitions/enum:CoreConfigurationParameterDataType"
                    },
                    "size": {
                        "default": 1,
                        "type": "integer",
                        "minimum": -2147483648,
                        "maximum": 2147483647
                    }
                }
            },
            "enum:CoreConfigurationParameterDataType": {
                "enum": ["CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64"]
            }
        },
        "$ref": "#/definitions/record:CoreConfiguration"
    }

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None
        self.defaultData = None

        self.name = ""
        self.namespace = ""
        self.description = ""

        self.orderedFields = []

        self.signature = 0xffffffff
        self.signatureBuffer = []

        self.valid = False
        self.reason = ""

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

            if self.__openJSON(jsonFile):
                if defaultFile is not None:
                    self.__openDefaultJSON(defaultFile)

            self.valid = self.__preProcess()  # sort the fields and calculate the signature

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::open: " + self.reason)
            return False

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
                formatString = formatString + field['size'] * TYPE_FORMAT_MAP[field['type']]

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

    FIELD_TYPE_ORDER = ["TIMESTAMP", "INT64", "UINT64", "FLOAT64", "INT32", "UINT32", "FLOAT32", "INT16", "UINT16", "CHAR", "INT8", "UINT8"]

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

    def __openJSON(self, jsonFile):
        CoreConsole.info("CONFIGURATION: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreConfiguration.SCHEMA)
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

    def __openDefaultJSON(self, jsonFile):
        CoreConsole.info("CONFIGURATION DEFAULT: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.defaultData = loadJson(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::openDefaultJSON: " + self.reason)
            return False

    def __preProcess(self):
        try:
            if self.valid:
                self.signatureBuffer = []
                self.orderedFields = []

                namespace = self.namespace
                for ns in namespace.split('::'):
                    self.signatureBuffer.append(ns)

                self.signatureBuffer.append(self.data['name'])

                fields = self.data['fields']
                for fieldType in self.FIELD_TYPE_ORDER:
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

    def __updateSignature(self):
        self.signature = (zlib.crc32(bytearray(':'.join(self.signatureBuffer), 'ascii')) & 0xffffffff)

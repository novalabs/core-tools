# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import zlib

from .CoreUtils import *


class CoreMessage:
    SCHEMA = {
        "definitions": {
            "record:CoreMessage": {
                "type": "object",
                "required": ["name", "description", "namespace", "fields"],
                "additionalProperties": False,
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
                "additionalProperties": False,
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
                "enum": ["CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64", "TIMESTAMP"]
            }
        },
        "$ref": "#/definitions/record:CoreMessage"
    }

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None

        self.name = ""
        self.namespace = ""
        self.description = ""

        self.orderedFields = []

        self.signature = 0xffffffff
        self.signatureBuffer = []

        self.valid = False
        self.reason = ""

    def open(self, name, package=None):
        self.__init__()

        if package is not None:
            jsonFile = package.getMessageFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            self.__openJSON(jsonFile)

            self.valid = self.__preProcess()  # sort the fields

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::open: " + self.reason)
            return False

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
        CoreConsole.info("MESSAGE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreMessage.SCHEMA)
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

    def __preProcess(self):
        try:
            if self.valid:
                self.signatureBuffer = []
                self.orderedFields = []

                fields = self.data['fields']
                for fieldType in self.FIELD_TYPE_ORDER:
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

# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreUtils import *


class CoreNode:
    SCHEMA = {
        "type": "object",
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
            "configuration": {
                "type": "string"
            },
            "publishers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string"
                        },
                        "description": {
                            "type": "string"
                        },
                        "type": {
                            "type": "string"
                        },
                        "notes": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "name",
                        "description",
                        "type"
                    ],
                    "additionalProperties": True,
                }
            },
            "subscribers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string"
                        },
                        "description": {
                            "type": "string"
                        },
                        "type": {
                            "type": "string"
                        }
                    },
                    "required": [
                        "name",
                        "description",
                        "type"
                    ],
                    "additionalProperties": True,
                }
            }
        },
        "required": [
            "name",
            "description",
            "namespace",
            "configuration"
        ]
    }

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None

        self.name = ""
        self.namespace = ""
        self.description = ""

        self.valid = False
        self.reason = ""

    def open(self, name, package=None):
        self.__init__()

        if package is not None:
            jsonFile = package.getNodeFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            self.__openJSON(jsonFile)

            self.valid = self.__preProcess()

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreNode::open: " + self.reason)
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

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

    def __openJSON(self, jsonFile):
        CoreConsole.info("NODE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreNode.SCHEMA)
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
                    CoreConsole.ok("CoreNode:: valid")
            else:
                raise CoreError("Node filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreNode::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def __preProcess(self):
        try:
            if self.valid:
                if 'publishers' in self.data:
                    for p in self.data['publishers']:
                        if not 'notes' in p:
                            p['notes'] = None
                else:
                    self.data['publishers'] = None

                if 'subscribers' in self.data:
                    for s in self.data['subscribers']:
                        if not 'notes' in s:
                            s['notes'] = None
                else:
                    self.data['subscribers'] = None

                return True
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreNode::preProcess: " + self.reason)
            return False

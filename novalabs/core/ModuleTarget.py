# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreUtils import *


class ModuleTarget:
    SCHEMA = {
        "definitions": {
            "record:ModuleTarget": {
                "type": "object",
                "required": [
                    "name",
                    "description",
                    "module",
                    "required_packages",
                    "sources",
                    "includes"
                ],
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "oneOf": [
                            {
                                "type": "null"
                            },
                            {
                                "$ref": "#/definitions/enum:TargetType"
                            }
                        ]
                    },
                    "name": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "module": {
                        "type": "string"
                    },
                    "os_version": {
                        "oneOf": [
                            {
                                "type": "null"
                            },
                            {
                                "$ref": "#/definitions/enum:OSVersion"
                            }
                        ]
                    },
                    "required_packages": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "required_os_components": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "includes": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "bootloader_size": {
                        "default": 0,
                        "type": "integer"
                    },
                    "configuration_size": {
                        "default": 0,
                        "type": "integer"
                    }
                }
            },
            "enum:OSVersion": {
                "enum": [
                    "CHIBIOS_3",
                    "CHIBIOS_16"
                ]
            },
            "enum:TargetType": {
                "enum": [
                    "bootloader",
                    "application"
                ]
            }
        },
        "$ref": "#/definitions/record:ModuleTarget"
    }

    DEFAULT_OS_VERSION = "CHIBIOS_16"

    def __init__(self):
        self.workspace = None

        self.targetName = ""
        self.root = None
        self.moduleTargetRoot = None
        self.source = ""

        self.data = None

        self.type = ""
        self.name = ""
        self.namespace = ""
        self.description = ""
        self.module = ""
        self.os_version = ""

        self.bootloader_size = 0
        self.configuration_size = 0

        self.valid = False
        self.reason = ""

        self.sources = None
        self.includes = None
        self.requiredPackages = []
        self.requiredOSComponents = []

        self.coreModule = None

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
            return self.__openJSON(filename)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ParametersTarget::open " + self.reason)

        self.valid = False
        return False

    def getRoot(self, cwd=None):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("MODULE_TARGET.json", cwd)
            if self.root is not None:
                CoreConsole.ok("ModuleTarget::getRoot: ModuleTarget found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "ModuleTarget::getRoot: Not inside a ModuleTarget"
                CoreConsole.fail(self.reason)

        return self.root

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
            return [self.type, CoreConsole.highlight(self.name), self.description, self.module, self.os_version, src, CoreConsole.success("OK")]
        else:
            return ["", "", "", "", "", src, CoreConsole.error(self.reason)]

    @staticmethod
    def getSummaryFields():
        return ["Type", "Name", "Description", "Module", "OS Version", "Root", "Status"]

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

    def __openJSON(self, jsonFile):
        CoreConsole.info("MODULE_TARGET: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, ModuleTarget.SCHEMA)
            if self.targetName == self.data["name"]:
                self.source = jsonFile

                if "type" in self.data:
                    self.type = self.data["type"]
                else:
                    self.type = "application"

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

                if "required_os_components" in self.data:
                    self.requiredOSComponents = []
                    for x in self.data["required_os_components"]:
                        self.requiredOSComponents.append(x)

                if "bootloader_size" in self.data:
                    self.bootloader_size = self.data["bootloader_size"]
                else:
                    self.bootloader_size = 0

                if "configuration_size" in self.data:
                    self.configuration_size = self.data["configuration_size"]
                else:
                    self.configuration_size = 0
                CoreConsole.ok("ModuleTarget:: valid")

                self.valid = True

                return True
            else:
                raise CoreError("Target filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("ModuleTarget::openJSON: " + self.reason)

        return False

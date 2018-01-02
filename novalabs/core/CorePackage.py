# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreConsole import *
from .CoreConfiguration import *
from .CoreMessage import *
from .CoreNode import *

import git


class CorePackage:
    schema = {
        "definitions": {
            "record:CorePackage": {
                "type": "object",
                "required": ["name", "description", "provider"],
                "additionalProperties": True,
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "description": {
                        "type": "string"
                    },
                    "provider": {
                        "type": "string"
                    }
                }
            }
        },
        "$ref": "#/definitions/record:CorePackage"
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

        self.valid = False
        self.reason = ""

        self.git_rev = None

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
            try:
                r = git.repo.Repo(self.packageRoot)
                self.git_rev = r.git.describe(all=True, long=True, dirty=True)
            except Exception as e:
                pass

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
            if not f.endswith(".default"):  # Skip
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

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

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

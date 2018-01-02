
# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreContainer import *
from .CoreBootstrap import fetch as UpdateCore


class Core(CoreContainer):
    schema = {
      "definitions" : {
        "record:Core" : {
          "type" : "object",
          "required" : [ "name", "description" ],
          "additionalProperties" : False,
          "properties" : {
            "name" : {
              "type" : "string"
            },
            "description" : {
              "type" : "string"
            }
          }
        }
      },
      "$ref" : "#/definitions/record:Core"
    }

    def __init__(self):
        CoreContainer.__init__(self)

        self.filename = ""
        self.root = None
        self.source = ""

        self.data = None

        self.name = ""
        self.description = ""

        self.destination = ""

        self.valid = False
        self.reason = ""

    def getRoot(self):
        if self.root is None:  # Check for cached value
            self.root = findFileGoingUp("CORE.json")
            if self.root is not None:
                CoreConsole.ok("Core::getRoot: Core found in " + CoreConsole.highlightFilename(self.root))
            else:
                self.reason = "Core::getRoot: Not inside a Core"
                CoreConsole.fail(self.reason)

        return self.root


    def openJSON(self, jsonFile):
        CoreConsole.info("CORE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, Core.schema)
            self.source = jsonFile
            self.name = self.data["name"]
            self.description = self.data["description"]

            self.valid = True

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("Core::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, root=None):
        self.valid = False

        try:
            if root is not None:
                self.root = root
            else:
                self.root = self.getRoot()

            if self.root is None:
                return False

            jsonFile = os.path.join(self.root, "CORE.json")

            if self.openJSON(jsonFile):
                self.openPackages()
                self.openModules()

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("Core::open: " + self.reason)

        return False

    def getPackagesRoot(self):
        return os.path.join(self.getRoot(), "packages")

    def getModulesRoot(self):
        return os.path.join(self.getRoot(), "modules")

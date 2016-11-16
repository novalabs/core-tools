#!/usr/bin/env python3

# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from json import loads
from sys import argv
from string import Template
from CoreUtils import *


class CoreNode:
    schema = '{ "type": "record", "name": "CoreNode", "fields": [ { "name": "name", "type": "string" }, { "name": "namespace", "type": "string" }, { "name": "description", "type": "string" }, { "name": "publishes", "type": { "type": "array", "items": { "type": "record", "name": "CoreNodeTopicP", "fields": [ { "name": "name", "type": "string" }, { "name": "message", "type": "string" }, { "name": "configuration", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "subscribes", "type": { "type": "array", "items": { "type": "record", "name": "CoreNodeTopicS", "fields": [ { "name": "name", "type": "string" }, { "name": "message", "type": "string" }, { "name": "configuration", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "configuration", "type": { "type": "array", "items": { "type": "record", "name": "CoreNodeConfiguration", "fields": [ { "name": "name", "type": "string" }, { "name": "parameters", "type": "string" }, { "name": "description", "type": "string" } ] } } } ] }'

    def __init__(self):
        self.package = None
        self.filename = ""
        self.source = ""

        self.data = None

        self.name = ""
        self.namespace = ""
        self.description = ""

        self.valid = False
        self.generated = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("NODE: " + CoreConsole.highlightFilename(jsonFile))
        try:
            self.data = loadAndValidateJson(jsonFile, CoreNode.schema)
            if self.filename == self.data["name"]:
                self.source = jsonFile
                self.name = self.data["name"]
                self.namespace = self.data["namespace"]
                self.description = self.data["description"]
                if self.namespace == "@" or self.namespace == "":
                    if self.package is not None:
                        self.namespace = self.package.name

                self.valid = True
            else:
                raise CoreError("Node filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreNode::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, name, package=None):
        if package is not None:
            jsonFile = package.getNodeFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            return self.openJSON(jsonFile)

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

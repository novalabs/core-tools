#!/usr/bin/env python

from avro.io import validate
from avro.schema import parse
from json import loads
from sys import argv
from string import Template
import sys
import os
from CoreUtils import *

class CoreNode:
    schema = '{ "type": "record", "name": "CoreNode", "fields": [ { "name": "name", "type": "string" }, { "name": "namespace", "type": "string" }, { "name": "description", "type": "string" }, { "name": "publishes", "type": { "type": "array", "items": { "type": "record", "name": "CoreNodeTopicP", "fields": [ { "name": "name", "type": "string" }, { "name": "message", "type": "string" }, { "name": "configuration", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "subscribes", "type": { "type": "array", "items": { "type": "record", "name": "CoreNodeTopicS", "fields": [ { "name": "name", "type": "string" }, { "name": "message", "type": "string" }, { "name": "configuration", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "configuration", "type": { "type": "array", "items": { "type": "record", "name": "CoreNodeConfiguration", "fields": [ { "name": "name", "type": "string" }, { "name": "parameters", "type": "string" }, { "name": "description", "type": "string" } ] } } } ] }'

    def __init__(self):
        self.data=[]
        self.source=""
        self.name = ""
        self.namespace = ""
        self.description = ""
        self.package = None

    def openJSON(self, filename):
        CoreConsole.info("NODE: " + CoreConsole.highlightFilename(filename))

        try:
            self.data = loadAndValidateJson(filename, CoreNode.schema)
            self.source = filename
            self.name = self.data["name"]
            self.namespace = self.data["namespace"]
            self.description = self.data["description"]
            if(self.namespace == "@"):
                if(self.package is not None):
                    self.namespace = self.package.namespace
        except CoreError as e:
            CoreConsole.fail("CoreNode: " + CoreConsole.highlightFilename(filename) + ": " + str(e.value))
            pass

    def open(self, package, name):
        filename = package.getNodeFile(name)

        try:
            self.package = package
            self.openJSON(filename)
        except CoreError:
            pass

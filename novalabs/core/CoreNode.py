# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from .CoreUtils import *


class CoreNode:
    schema = {
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
          "additionalProperties" : True,
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
          "additionalProperties" : True,
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

        self.docDestination = ""

        self.buffer = []

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

    def open(self, name, package=None):
        self.__init__()

        if package is not None:
            jsonFile = package.getNodeFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            self.openJSON(jsonFile)

            self.valid = self.preProcess()

            return self.valid
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreNode::open: " + self.reason)
            return False

    def generateDocumentation(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "doc", "nodes")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.name + ".adoc"))

                    self.processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreNode::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreNode::generateDocumentation: " + self.reason)
            return False

        return True

    def generate(self, path):
        if not self.generateDocumentation(path):
            return False

        return True

    def preProcess(self):
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

    def __processDocumentationPreamble(self):
        t = """
[[anchor_node-{namespace}::{data[name]}]]
=== {namespace}::{data[name]}
_{data[description]}_

Configuration: <<anchor_params-{data[configuration]}>>
"""
        s = SuperFormatter()
        self.buffer.append(s.format(t, namespace=self.namespace, data=self.data))

        tmp, dummy = os.path.splitext(self.source)
        addDocFile = tmp + ".adoc"

        if os.path.exists(addDocFile):
            with open(addDocFile, "r") as f:
                t = f.read()
                s = SuperFormatter()
                self.buffer.append(s.format(t, namespace=self.namespace, name=self.data['name'], provider=self.package.provider, package=self.package.name, fqn=self.namespace + "::" + self.data['name']))

    def __processDocumentationEnd(self):
        pass

    def __processDocumentationFields(self, title, data):
        t_begin = """
[cols="15,55,30", options="header"]
.{namespace}::{data[name]} {title}
|===

| Topic | Description | Type
        """
        t_field = """.2+^.^| `{field[name]}` | {field[description]} |<<{refdoc}#anchor-msg-{field[type]},`{field[type]}`>>
    2+| {emit_notes:if:
_{field[notes]}_}"""

        t_end = """
|===
"""
        s = SuperFormatter()

        self.buffer.append(s.format(t_begin, title=title,  namespace=self.namespace, data=self.data))

        for field in data:
            tmp = splitFQN(field['type'])
            refdoc = "../" + ("/".join(tmp[1:-1])) + "/index.adoc"

            self.buffer.append(s.format(t_field, refdoc=refdoc, field=field, emit_notes=field['notes'] is not None))

        self.buffer.append(s.format(t_end, namespace=self.namespace, data=data, json=self.source))

    def __processDocumentationPublishers(self):
        if self.data['publishers'] is not None:
            self.__processDocumentationFields("Publishers", self.data['publishers'])
        if self.data['subscribers'] is not None:
            self.__processDocumentationFields("Subscribers", self.data['subscribers'])

    def processDocumentation(self):
        self.buffer = []
        if self.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationPublishers()
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
                docDst = os.path.relpath(self.docDestination, relpathDst)
            else:
                docDst = self.docDestination

            if self.generated:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, docDst]
            else:
                return [CoreConsole.highlight(self.namespace), CoreConsole.highlight(self.name), self.description, src, CoreConsole.error(self.reason)]
        else:
            return ["", "", CoreConsole.error(self.reason), "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generated doc"]

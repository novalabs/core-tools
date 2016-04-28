from CoreUtils import *


class CoreMessage:
    schema = '{ "type": "record", "name": "CoreMessage", "namespace" : "", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "namespace", "type": "string" }, { "name": "fields", "type": { "type": "array", "items": { "type": "record", "name": "CoreConfigurationParameter", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "type", "type": { "type": "enum", "name": "CoreConfigurationParameterDataType", "symbols": [ "CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64", "TIMESTAMP" ] } }, { "name": "size", "type": "int", "default": 1 } ] } } } ] }'

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

        self.valid = False
        self.generated = False
        self.reason = ""

    def openJSON(self, jsonFile):
        CoreConsole.info("MESSAGE: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreMessage.schema)
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
                raise CoreError("Message filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, name, package = None):
        if package is not None:
            jsonFile = package.getMessageFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            return self.openJSON(jsonFile)

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::open: " + self.reason)
            return False

    def generate(self, path):
        self.generated = False

        try:
            if self.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "include", self.package.name)
                    else:
                        path = path

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.destination = os.path.join(path, (self.name + ".hpp"))

                    self.process()

                    sink = open(self.destination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreMessage::generate " + CoreConsole.highlightFilename(self.destination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::generate: " + self.reason)
            return False

        return True

    def process(self):
        self.buffer = []
        if self.valid:
            self.__processPreamble()
            self.__processNamsepaceBegin()
            self.__processMessageBegin()
            self.__processFields()
            self.__processMessageEnd()
            self.__processNamsepaceEnd()

    def __processPreamble(self):
        self.buffer.append('#pragma once')
        self.buffer.append('')
        self.buffer.append('#include <Core/MW/CoreMessage.hpp>')
        self.buffer.append('')

    def __processNamsepaceBegin(self):
        namespace = self.namespace
        for ns in namespace.split('::'):
            self.buffer.append('namespace ' + ns + ' {')
        self.buffer.append('')

    def __processMessageBegin(self):
        self.buffer.append('CORE_MESSAGE_BEGIN(' + self.data['name'] + ') //' + self.data['description'])

    def __processFields(self):
        fields = self.data['fields']
        for field in fields:
            self.buffer.append('	CORE_MESSAGE_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'])

    def __processMessageEnd(self):
        self.buffer.append('CORE_MESSAGE_END')

    def __processNamsepaceEnd(self):
        namespace = self.data['namespace']
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')

    def getSummary(self, relpath = None):
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

    def getSummaryGenerate(self, relpathSrc = None, relpathDst = None):
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

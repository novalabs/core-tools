from CoreUtils import *


class CoreConfiguration:
    schema = '{ "type": "record", "name": "CoreConfiguration", "namespace" : "", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "namespace", "type": "string" }, { "name": "fields", "type": { "type": "array", "items": { "type": "record", "name": "CoreConfigurationParameter", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "type", "type": { "type": "enum", "name": "CoreConfigurationParameterDataType", "symbols": [ "CHAR", "INT8", "UINT8", "INT16", "UINT16", "INT32", "UINT32", "INT64", "UINT64", "FLOAT32", "FLOAT64" ] } }, { "name": "size", "type": "int", "default": 1 } ] } } } ] }'

    def __init__(self):
        self.data = []
        self.package = None
        self.filename = ""
        self.source = ""
        self.name = ""
        self.namespace = ""
        self.description = ""
        self.destination = ""
        self.valid = False
        self.reason = ""
        self.buffer = []

    def openJSON(self, jsonFile):
        CoreConsole.info("CONFIGURATION: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreConfiguration.schema)
            if (self.filename == self.data["name"]):
                self.source = jsonFile
                self.name = self.data["name"]
                self.namespace = self.data["namespace"]
                self.description = self.data["description"]
                if (self.namespace == "@" or self.namespace == ""):
                    if (self.package is not None):
                        self.namespace = self.package.name

                self.valid = True
                return True
            else:
                raise CoreError("Configuration filename/name mismatch", jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::openJSON: " + self.reason)
            self.valid = False
            return False

        return True

    def open(self, name, package=None):
        if package is not None:
            jsonFile = package.getConfigurationFile(name)
        else:
            jsonFile = name

        try:
            self.package = package
            self.filename = getFileName(jsonFile)

            return self.openJSON(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::open: " + self.reason)
            return False

        return True

    def generate(self, path):
        try:
            if (self.valid):
                if (path == ""):
                    raise CoreError("'out' file is empty")
                try:
                    if self.package is not None:
                        path = os.path.join(path, self.package.name, "include", self.package.name)
                    else:
                        path = path

                    if (not os.path.isdir(path)):
                        os.makedirs(path)

                    self.destination = os.path.join(path, (self.name + ".hpp"))

                    self.process()

                    sink = open(self.destination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generate " + CoreConsole.highlightFilename(self.destination))

                    return True
                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generate: " + self.reason)
            return False

        return True

    def process(self):
        self.buffer = []
        if (self.valid):
            self.__processPreamble()
            self.__processNamsepaceBegin()
            self.__processConfigurationBegin()
            self.__processFields()
            self.__processMapBegin()
            self.__processMapFields()
            self.__processMapEnd()
            self.__processConfigurationEnd()
            self.__processNamsepaceEnd()

    def __processPreamble(self):
        self.buffer.append('#pragma once')
        self.buffer.append('')
        self.buffer.append('#include <Core/MW/CoreConfiguration.hpp>')
        self.buffer.append('')

    def __processNamsepaceBegin(self):
        namespace = self.namespace
        for ns in namespace.split('::'):
            self.buffer.append('namespace ' + ns + ' {')
        self.buffer.append('')

    def __processConfigurationBegin(self):
        self.buffer.append('CORE_CONFIGURATION_BEGIN(' + self.data['name'] + ') //' + self.data['description'])

    def __processFields(self):
        fields = self.data['fields']
        for field in fields:
            self.buffer.append('	CORE_CONFIGURATION_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'])

    def __processMapBegin(self):
        fields = self.data['fields']
        self.buffer.append('CORE_CONFIGURATION_MAP_BEGIN(' + str(len(fields)) + ')')

    def __processMapFields(self):
        fields = self.data['fields']
        for field in fields:
            self.buffer.append('	CORE_CONFIGURATION_MAP_ENTRY(' + self.data['name'] + ', ' + field['name'] + ')')

    def __processMapEnd(self):
        self.buffer.append('CORE_CONFIGURATION_MAP_END()')

    def __processConfigurationEnd(self):
        self.buffer.append('CORE_CONFIGURATION_END()')

    def __processNamsepaceEnd(self):
        namespace = self.data['namespace']
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')

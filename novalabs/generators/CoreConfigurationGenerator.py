# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from novalabs.core.CoreTypes import *
from novalabs.core.CoreUtils import *
from novalabs.core import CoreConfiguration

import copy
import json

class CoreConfigurationGenerator :
    def __init__(self, obj : CoreConfiguration):
        self.object = obj

        self.generated = False
        self.reason = ""

        self.hppDestination = ""
        self.cppDestination = ""
        self.docDestination = ""
        self.schemaDestination = ""

        self.schema = dict()

        self.buffer = []

    def generate(self, path):
        if not self.__generateHeader(path):
            return False

        if not self.__generateSource(path):
            return False

        if not self.__generateDocumentation(path):
            return False

        if not self.__generateSchema(path):
            return False

        for field in self.object.data['fields']:
            if len(field['name']) > 16:
                self.reason = "Field name " + field['name'] + " is too long"
                self.generated = False
                return False

        return True

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        if self.object.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.object.source, relpathSrc)
            else:
                src = self.object.source

            if relpathDst is not None:
                hppDst = os.path.relpath(self.hppDestination, relpathDst)
                cppDst = os.path.relpath(self.cppDestination, relpathDst)
                docDst = os.path.relpath(self.docDestination, relpathDst)
            else:
                hppDst = self.hppDestination
                cppDst = self.cppDestination
                docDst = self.docDestination

            if self.generated:
                return [CoreConsole.highlight(self.object.namespace), CoreConsole.highlight(self.object.name), self.object.description, src, hppDst, cppDst, docDst]
            else:
                return [CoreConsole.highlight(self.object.namespace), CoreConsole.highlight(self.object.name), self.object.description, src, CoreConsole.error(self.reason), "", ""]
        else:
            return ["", "", CoreConsole.error(self.reason), "", "", "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generated hpp", "Generated cpp", "Generated doc"]

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

    def __generateHeader(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.object.package is not None:
                        path = os.path.join(path, self.object.package.name, "include", self.object.package.provider, self.object.package.name)
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.hppDestination = os.path.join(path, (self.object.name + ".hpp"))

                    self.__processHeader()

                    sink = open(self.hppDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateHeader " + CoreConsole.highlightFilename(self.hppDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generate: " + self.reason)
            return False

        return True

    def __generateSource(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.object.package is not None:
                        path = os.path.join(path, self.object.package.name, "src")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.cppDestination = os.path.join(path, (self.object.name + ".cpp"))

                    self.__processSource()

                    sink = open(self.cppDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateSource " + CoreConsole.highlightFilename(self.cppDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generate: " + self.reason)
            return False

        return True

    def __generateDocumentation(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.object.package is not None:
                        path = os.path.join(path, self.object.package.name, "doc", "params")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.object.name + ".adoc"))

                    self.__processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreConfiguration::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generateDocumentation: " + self.reason)
            return False

        return True

    def __generateSchema(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.object.package is not None:
                        path = os.path.join(path, self.object.package.name, "schema", self.object.package.provider, self.object.package.name)
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.schemaDestination = os.path.join(path, (self.object.name + ".json"))

                    self.__processSchema()

                    sink = open(self.schemaDestination, 'w')
                    sink.write(json.dumps(self.schema, indent=4, separators=(',', ': ')))

                    CoreConsole.ok("CoreConfiguration::generateSchema " + CoreConsole.highlightFilename(self.schemaDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreConfiguration::generateSchema: " + self.reason)
            return False

        return True

    def __processHeader(self):
        self.buffer = []

        if self.object.valid:
            self.__processHeaderPreamble()
            self.__processNamsepaceBegin()
            self.__processConfigurationBegin()
            self.buffer.append("// --- FIELDS -----------------------------------------------------------------")
            self.__processFields()
            self.buffer.append("// ----------------------------------------------------------------------------")
            self.__processConfigurationSignature()
            self.__processConfigurationLength()
            self.__processConfigurationEnd()
            self.__processNamsepaceEnd()

    def __processSource(self):
        self.buffer = []

        if self.object.valid:
            self.__processSourcePreamble()
            self.__processNamsepaceBegin()
            self.__processDefaultBegin()
            self.__processDefaultFields()
            self.__processDefaultEnd()
            self.__processConstructor()
            self.__processMapBegin()
            self.__processMapFields()
            self.__processMapEnd()
            self.__processNamsepaceEnd()

    def __processDocumentation(self):
        self.buffer = []
        if self.object.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationFields()
            self.__processDocumentationEnd()

    def __processSchema(self):
        self.buffer = []
        if self.object.valid:
            self.__processSchemaPreamble()
            self.__processSchemaFields()
            self.__processSchemaEnd()

    def __processHeaderPreamble(self):
        self.buffer.append('#pragma once')
        self.buffer.append('')
        self.buffer.append('#include <core/mw/CoreConfiguration.hpp>')
        self.buffer.append('')

    def __processSourcePreamble(self):
        self.buffer.append('#include <' + os.path.join(self.object.package.provider, self.object.package.name, self.object.name + '.hpp') + '>')
        self.buffer.append('')

    def __processNamsepaceBegin(self):
        namespace = self.object.namespace
        for ns in namespace.split('::'):
            self.buffer.append('namespace ' + ns + ' {')
        self.buffer.append('')

    def __processConfigurationBegin(self):
        self.buffer.append('CORE_CONFIGURATION_BEGIN(' + self.object.data['name'] + ') //' + self.object.data['description'])

    def __processFields(self):
        fields = self.object.orderedFields
        for field in fields:
            self.buffer.append('	CORE_CONFIGURATION_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'] + ' [' + (str(field['default']) if field['default'] is not None else '') + ']')

    def __processConstructor(self):
        self.buffer.append('CORE_CONFIGURATION_CONSTRUCTOR_BEGIN(' + self.object.data['name'] + ')')

        buffer = ""
        fields = self.object.orderedFields
        for field in fields:
            if field['default'] is not None:
                buffer = buffer + '	CORE_CONFIGURATION_CONSTRUCTOR_FIELD(' + field['name'] + '), ' + "\n"
            else:
                buffer = buffer + '	CORE_CONFIGURATION_CONSTRUCTOR_FIELD_NONE(' + field['name'] + '), ' + "\n"
        buffer = buffer[:-3]

        self.buffer.append(buffer)

        self.buffer.append('CORE_CONFIGURATION_CONSTRUCTOR_END()')
        self.buffer.append('')

    def __processDefaultBegin(self):
        self.buffer.append('CORE_CONFIGURATION_DEFAULT_BEGIN()')

    def __processDefaultFields(self):
        fields = self.object.orderedFields
        for field in fields:
            if field['default'] is not None:
                self.buffer.append('	CORE_CONFIGURATION_DEFAULT_FIELD(' + field['name'] + ', ' + field['type'] + ', ' +  str(field['size']) + ', ' + formatValuesAsC(field['type'], field['size'], field['default']) + ')')

    def __processDefaultEnd(self):
        self.buffer.append('CORE_CONFIGURATION_DEFAULT_END()')
        self.buffer.append('')

    def __processMapBegin(self):
        name = self.object.data['name']
        self.buffer.append('CORE_CONFIGURATION_MAP_BEGIN(' + name + ')')

    def __processMapFields(self):
        fields = self.object.data['fields']
        for field in fields:
            self.buffer.append('	CORE_CONFIGURATION_MAP_ENTRY(' + self.object.data['name'] + ', ' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ')')

    def __processMapEnd(self):
        self.buffer.append('CORE_CONFIGURATION_MAP_END()')

    def __processConfigurationSignature(self):
        self.buffer.append('CORE_CONFIGURATION_SIGNATURE(' + hex(self.object.signature) + ')')

    def __processConfigurationLength(self):
        fields = self.object.data['fields']
        self.buffer.append('CORE_CONFIGURATION_LENGTH(' + str(len(fields)) + ')')

    def __processConfigurationEnd(self):
        self.buffer.append('CORE_CONFIGURATION_END()')

    def __processNamsepaceEnd(self):
        namespace = self.object.namespace
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')
        self.buffer.append('')

    def __processDocumentationPreamble(self):
        t = """
[[anchor_params-{namespace}::{data[name]}]]
=== {namespace}::{data[name]}
_{data[description]}_
"""
        s = SuperFormatter()
        self.buffer.append(s.format(t, namespace=self.object.namespace, data=self.object.data))

    def __processDocumentationEnd(self):
        tmp, dummy = os.path.splitext(self.object.source)
        addDocFile = tmp + ".adoc"

        if os.path.exists(addDocFile):
            with open(addDocFile, "r") as f:
                t = f.read()
                s = SuperFormatter()
                self.buffer.append(s.format(t, namespace=self.object.namespace, name=self.object.data['name'], provider=self.object.package.provider, package=self.object.package.name, fqn=self.object.namespace + "::" + self.object.data['name']))

    def __processDocumentationFields(self):
        t_begin = """
[cols="20,62,10,8", options="header"]
.{namespace}::{data[name]}
|===

| Field | Description | Type | Size
        """
        t_field = """.2+^.^| `{field[name]}` | {field[description]} | `{field[type]}` | {field[size]}
    3+| {emit_default:if:Default: `{field[default]}`} {emit_notes:if:+
_{field[notes]}_}"""

        t_end = """
|===
"""
        s = SuperFormatter()

        self.buffer.append(s.format(t_begin, namespace=self.object.namespace, data=self.object.data))

        for field in self.object.data['fields']:
            self.buffer.append(s.format(t_field, field=field, emit_notes=field['notes'] is not None,  emit_default=field['default'] is not None))

        self.buffer.append(s.format(t_end, namespace=self.object.namespace, data=self.object.data, json=self.object.source))

    def __processSchemaPreamble(self):
        self.schema['definitions'] = copy.deepcopy(CORE_TYPE_JSON_DEFINITIONS)
        self.schema['type'] = 'object'
        self.schema['required'] = list()
        self.schema['additionalProperties'] = True

    def __processSchemaEnd(self):
        pass

    def __processSchemaFields(self):
        self.schema['properties'] = dict()

        for field in self.object.data['fields']:
            self.schema['properties'][field['name']] = getJSONSchemaElementForCoreType(field['type'], field['size'])
            if field['default'] is not None:
                self.schema['properties'][field['name']]['default'] = field['default']
            else:
                self.schema['required'].append(field['name'])






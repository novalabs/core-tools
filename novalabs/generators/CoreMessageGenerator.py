# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from novalabs.core.CoreUtils import *
from novalabs.core import CoreMessage


class CoreMessageGenerator :
    def __init__(self, obj : CoreMessage):
        self.object = obj

        self.generated = False
        self.reason = ""

        self.hppDestination = ""
        self.cppDestination = ""
        self.docDestination = ""

        self.buffer = []

    def generate(self, path):
        if not self.__generateHeader(path):
            return False

        if not self.__generateDocumentation(path):
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
                docDst = os.path.relpath(self.docDestination, relpathDst)
            else:
                hppDst = self.hppDestination
                docDst = self.docDestination

            if self.generated:
                return [CoreConsole.highlight(self.object.namespace), CoreConsole.highlight(self.object.name), self.object.description, src, hppDst, docDst]
            else:
                return [CoreConsole.highlight(self.object.namespace), CoreConsole.highlight(self.object.name), self.object.description, src, CoreConsole.error(self.reason), ""]
        else:
            return ["", "", CoreConsole.error(self.reason), "", "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generated hpp", "Generated doc"]

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
                        path = path

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.hppDestination = os.path.join(path, (self.object.name + ".hpp"))

                    self.__process()

                    sink = open(self.hppDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreMessage::generate " + CoreConsole.highlightFilename(self.hppDestination))

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

    def __generateDocumentation(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.object.package is not None:
                        path = os.path.join(path, self.object.package.name, "doc", "msgs")
                    else:
                        raise CoreError("Implementation changed. 'self.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.object.name + ".adoc"))

                    self.__processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CoreMessage::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreMessage::generateDocumentation: " + self.reason)
            return False

        return True

    def __process(self):
        self.buffer = []
        if self.object.valid:
            self.__processPreamble()
            self.__processNamsepaceBegin()
            self.__processMessageBegin()
            self.__processFields()
            self.__processMessageSignature()
            self.__processMessageEnd()
            self.__processNamsepaceEnd()

    def __processDocumentation(self):
        self.buffer = []
        if self.object.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationFields()
            self.__processDocumentationEnd()

    def __processPreamble(self):
        self.buffer.append('#pragma once')
        self.buffer.append('')
        self.buffer.append('#include <core/mw/CoreMessage.hpp>')
        self.buffer.append('')

    def __processNamsepaceBegin(self):
        namespace = self.object.namespace
        for ns in namespace.split('::'):
            self.buffer.append('namespace ' + ns + ' {')
        self.buffer.append('')

    def __processMessageBegin(self):
        self.buffer.append('CORE_MESSAGE_BEGIN(' + self.object.data['name'] + ') //' + self.object.data['description'])

    def __processFields(self):
        fields = self.object.orderedFields
        for field in fields:
            self.buffer.append('	CORE_MESSAGE_FIELD(' + field['name'] + ', ' + field['type'] + ', ' + str(field['size']) + ') // ' + field['description'])

    def __processMessageSignature(self):
        self.buffer.append('CORE_MESSAGE_SIGNATURE(' + hex(self.object.signature) + ')')

    def __processMessageEnd(self):
        self.buffer.append('CORE_MESSAGE_END')

    def __processNamsepaceEnd(self):
        namespace = self.object.namespace
        self.buffer.append('')
        for ns in namespace.split('::'):
            self.buffer.append('}')

    def __processDocumentationPreamble(self):
        t = """
[[anchor_msg-{namespace}::{data[name]}]]
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
    3+| {emit_notes:if:+
_{field[notes]}_}"""

        t_end = """
|===
"""
        s = SuperFormatter()

        self.buffer.append(s.format(t_begin, namespace=self.object.namespace, data=self.object.data))

        for field in self.object.data['fields']:
            self.buffer.append(s.format(t_field, field=field, emit_notes=field['notes'] is not None))

        self.buffer.append(s.format(t_end, namespace=self.object.namespace, data=self.object.data, json=self.object.source))






# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from novalabs.core.CoreUtils import *
from novalabs.core import CoreMessage


class CoreNodeGenerator :
    def __init__(self, obj : CoreMessage):
        self.object = obj

        self.generated = False
        self.reason = ""

        self.docDestination = ""

        self.buffer = []

    def generate(self, path):
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
                docDst = os.path.relpath(self.docDestination, relpathDst)
            else:
                docDst = self.docDestination

            if self.generated:
                return [CoreConsole.highlight(self.object.namespace), CoreConsole.highlight(self.object.name), self.object.description, src, docDst]
            else:
                return [CoreConsole.highlight(self.object.namespace), CoreConsole.highlight(self.object.name), self.object.description, src, CoreConsole.error(self.reason)]
        else:
            return ["", "", CoreConsole.error(self.reason), "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["NS", "Name", "Description", "Root", "Generated doc"]

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

    def __generateDocumentation(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    if self.object.package is not None:
                        path = os.path.join(path, self.object.package.name, "doc", "nodes")
                    else:
                        raise CoreError("Implementation changed. 'self.object.package' MUST be defined")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.object.name + ".adoc"))

                    self.__processDocumentation()

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

    def __processDocumentationPreamble(self):
        t = """
[[anchor_node-{namespace}::{data[name]}]]
=== {namespace}::{data[name]}
_{data[description]}_

Configuration: <<anchor_params-{data[configuration]}>>
"""
        s = SuperFormatter()
        self.buffer.append(s.format(t, namespace=self.object.namespace, data=self.object.data))

        tmp, dummy = os.path.splitext(self.object.source)
        addDocFile = tmp + ".adoc"

        if os.path.exists(addDocFile):
            with open(addDocFile, "r") as f:
                t = f.read()
                s = SuperFormatter()
                self.buffer.append(s.format(t, namespace=self.object.namespace, name=self.object.data['name'], provider=self.object.package.provider, package=self.object.package.name, fqn= self.object.namespace + "::" + self.object.data['name']))

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

        self.buffer.append(s.format(t_begin, title=title,  namespace=self.object.namespace, data=self.object.data))

        for field in data:
            tmp = splitFQN(field['type'])
            refdoc = "../" + ("/".join(tmp[1:-1])) + "/index.adoc"

            self.buffer.append(s.format(t_field, refdoc=refdoc, field=field, emit_notes=field['notes'] is not None))

        self.buffer.append(s.format(t_end, namespace=self.object.namespace, data=data, json=self.object.source))

    def __processDocumentationPublishers(self):
        if self.object.data['publishers'] is not None:
            self.__processDocumentationFields("Publishers", self.object.data['publishers'])
        if self.object.data['subscribers'] is not None:
            self.__processDocumentationFields("Subscribers", self.object.data['subscribers'])

    def __processDocumentation(self):
        self.buffer = []
        if self.object.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationPublishers()
            self.__processDocumentationEnd()


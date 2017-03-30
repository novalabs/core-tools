# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

from novalabs.core.CoreUtils import *
from novalabs.core import CorePackage


class CorePackageGenerator:
    def __init__(self, obj: CorePackage):
        self.object = obj

        self.generated = False
        self.reason = ""

        self.destination = ""
        self.hppDestination = ""
        self.docDestination = ""

        self.buffer = []

        self.cmake = ""
        self.cmakePathPrefix = None
        self.sources = []
        self.cmakeSources = []
        self.includes = []
        self.link = False

    def generate(self, path, cmakePathPrefix=None, link=False):
        if not self.__generatePackage(path, cmakePathPrefix, link):
            return False

        if not self.__generateDocumentation(path):
            return False

        self.generated = True

        return True

    def getSummaryGenerate(self, relpathSrc=None, relpathDst=None):
        if self.object.valid:
            if relpathSrc is not None:
                src = os.path.relpath(self.object.packageRoot, relpathSrc)
            else:
                src = self.object.packageRoot

            if relpathDst is not None:
                dst = os.path.relpath(self.destination, relpathDst)
            else:
                dst = self.destination

            if self.link:
                dst = dst + CoreConsole.highlight(" [LINKS]")

            if self.generated:
                return [CoreConsole.highlight(self.object.name), self.object.description, self.object.provider, src, dst]
            else:
                return [CoreConsole.highlight(self.object.name), self.object.description, self.object.provider, src, CoreConsole.error(self.reason)]
        else:
            return ["", CoreConsole.error(self.reason), "", "", ""]

    @staticmethod
    def getSummaryFieldsGenerate():
        return ["Name", "Description", "Provider", "Root", "Generate"]

    # ---------------------------------------------------------------------------- #
    # --- PRIVATE ---------------------------------------------------------------- #
    # ---------------------------------------------------------------------------- #

    def __generatePackage(self, path, cmakePathPrefix=None, link=False):
        self.cmakePathPrefix = cmakePathPrefix
        self.generated = False
        self.link = link

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    path = os.path.join(path, self.object.name)

                    self.destination = path

                    if not os.path.isdir(self.destination):
                        os.makedirs(self.destination)

                    self.__process()

                    CoreConsole.ok("CorePackage::generate " + CoreConsole.highlightFilename(self.destination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::generate: " + self.reason)
            return False

        return True

    def __generateDocumentation(self, path):
        self.generated = False

        try:
            if self.object.valid:
                if path == "":
                    raise CoreError("'out' file is empty")
                try:
                    path = os.path.join(path, self.object.name, "doc")

                    if not os.path.isdir(path):
                        os.makedirs(path)

                    self.docDestination = os.path.join(path, (self.object.name + ".adoc"))

                    self.processDocumentation()

                    sink = open(self.docDestination, 'w')
                    sink.write("\n".join(self.buffer))

                    CoreConsole.ok("CorePackage::generateDocumentation " + CoreConsole.highlightFilename(self.docDestination))

                    self.generated = True

                except IOError as e:
                    raise CoreError(str(e.strerror), e.filename)
            else:
                return False

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CorePackage::generateDocumentation: " + self.reason)
            return False

        return True

    def __process(self):
        srcIncludes = os.path.join(self.object.packageRoot, "include")
        dstIncludes = os.path.join(self.destination, "include", self.object.provider, self.object.name)

        self.includes = listFiles(srcIncludes)
        if len(self.includes) > 0:
            if not os.path.isdir(dstIncludes):
                os.makedirs(dstIncludes)
            for file in self.includes:
                copyOrLink(os.path.join(srcIncludes, file), os.path.join(dstIncludes, file), link=self.link)

        srcSources = os.path.join(self.object.packageRoot, "src")
        dstSources = os.path.join(self.destination, "src")

        self.sources = listFiles(srcSources)
        if len(self.sources) > 0:
            if not os.path.isdir(dstSources):
                os.makedirs(dstSources)
            for file in self.sources:
                copyOrLink(os.path.join(srcSources, file), os.path.join(dstSources, file), link=self.link)

        self.cmakeSources = listFiles(srcSources)

        for conf in self.object.listConfigurationFiles():
            self.cmakeSources.append(conf + ".cpp")  # TODO: now we assume that it will be generated...

        self.__processCMake()

        self.cmake = os.path.join(self.destination, self.object.name + "Config.cmake")
        sink = open(self.cmake, 'w')

        sink.write("\n".join(self.buffer))

    def __processCMake(self):
        self.buffer = []

        if self.cmakePathPrefix is None:
            self.buffer.append('LIST( APPEND WORKSPACE_PACKAGES_MODULES ' + self.object.name + ' )')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.object.name + '_SOURCES')
            for src in self.cmakeSources:
                self.buffer.append('  ' + os.path.join(self.destination, "src", src))
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.object.name + '_INCLUDES')
            self.buffer.append('  ' + os.path.join(self.destination, "include"))
            self.buffer.append(')')
            self.buffer.append('')
        else:
            self.buffer.append('LIST( APPEND WORKSPACE_PACKAGES_MODULES ' + self.object.name + ' )')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.object.name + '_SOURCES')
            for src in self.cmakeSources:
                self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.object.name + "/src/" + src)
            self.buffer.append(')')

            self.buffer.append('SET( WORKSPACE_PACKAGES_' + self.object.name + '_INCLUDES')
            self.buffer.append('  ' + self.cmakePathPrefix + '/' + self.object.name + "/include")
            self.buffer.append(')')
            self.buffer.append('')

    def __processDocumentationPreamble(self):
        t = """
[[anchor_pack-{provider}::{package}]]
== {provider}::{package}
_{description}_
"""
        s = SuperFormatter()
        self.buffer.append(s.format(t, package=self.object.name, provider=self.object.provider, description=self.object.description))

        tmp, dummy = os.path.splitext(self.object.source)
        addDocFile = os.path.join(self.object.packageRoot, self.object.name + ".adoc")

        if os.path.exists(addDocFile):
            with open(addDocFile, "r") as f:
                t = f.read()
                s = SuperFormatter()
                self.buffer.append(s.format(t, name=self.object.name, provider=self.object.provider, package=self.object.name, fqn=self.object.provider + "::" + self.object.name))

    def __processDocumentationEnd(self):
        pass

    def processDocumentation(self):
        self.buffer = []
        if self.object.valid:
            self.__processDocumentationPreamble()
            self.__processDocumentationEnd()

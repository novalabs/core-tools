# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import shutil
import sys
import os
import numbers
import ctypes
from json import loads
import jsonschema
from jsonschema import validate

from .CoreConsole import *

class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class CoreError(Exception):
    def __init__(self, value, file=None, context=None):
        self.value = value
        self.context = context
        self.file = file

    def __str__(self):
        tmp = ""

        if self.context is not None:
            tmp += self.context + ": "

        tmp += repr(self.value)

        if self.file is not None:
            tmp += " [" + CoreConsole.highlightFilename(self.file) + "]"

        return tmp


def getFileName(x):
    (dummy, name) = os.path.split(x)
    (name, dummy) = os.path.splitext(name)

    return name


def listFilesByExtension(path, extension):
    tmp = []

    if os.path.isdir(path):
        for file in os.listdir(path):
            if file.endswith(extension):
                tmp.append(file)

    tmp.sort()
    return tmp


def listFiles(path):
    tmp = []

    if os.path.isdir(path):
        for file in os.listdir(path):
            if os.path.isfile(os.path.join(path, file)):  # Skip directorties
                tmp.append(file)

    tmp.sort()
    return tmp


def listDirectories(path, fullpath=False):
    tmp = []

    if os.path.isdir(path):
        for file in os.listdir(path):
            x = os.path.join(path, file)
            if os.path.isdir(x):
                if fullpath:
                    tmp.append(x)
                else:
                    tmp.append(file)

    tmp.sort()
    return tmp


def listFilesByAndStripExtension(path, extension):
    tmp = []

    if os.path.isdir(path):
        for file in os.listdir(path):
            if file.endswith(extension):
                (h, e) = os.path.splitext(file)
                (h, f) = os.path.split(h)
                tmp.append(f)

    tmp.sort()
    return tmp


def loadJson(filename):
    try:
        return loads(open(filename, 'r').read())
    except IOError as e:
        raise CoreError("I/0 Error: " + str(e.strerror), e.filename)


def loadAndValidateJson(filename, schema):
    try:
        data = loads(open(filename, 'r').read())
        validate(data, schema)
        return data
    except jsonschema.exceptions.ValidationError as e:
        raise CoreError("File invalid according to schema [%s]" % e.message, filename)
    except ValueError:
        raise CoreError("Broken JSON file", filename)
    except IOError as e:
        raise CoreError("I/0 Error: " + str(e.strerror), e.filename)


def splitFQN(x):
    return x.split("::")


def findFileGoingUp(filename, cwd=None):
    if cwd is None:
        cwd = os.getcwd()

    root = None
    (drive, tail) = os.path.splitdrive(cwd)
    drive = drive + os.sep

    while cwd != drive:
        if os.path.isfile(os.path.join(cwd, filename)):
            root = cwd
            break

        (cwd, t) = os.path.split(cwd)

    if root is not None:
        return root.replace("\\", "/")
    else:
        return root


def copyOrLink(src, dst, rm=True, link=False):
    env_link = os.environ.get("NOVA_CORE_LINKS_NOT_COPIES")

    if env_link is not None:  # Ok, it is defined. It overrides the parameter
        link = True

    if link:
        if os.path.islink(dst):
            if os.path.realpath(src) == os.path.realpath(dst):
                return
        if rm:
            if os.path.exists(dst):
                os.unlink(dst)

        os.symlink(src, dst)
    else:
        if rm:
            if os.path.exists(dst):
                os.unlink(dst)
        shutil.copy2(src, dst)


def mkdir(tmp):
    if not os.path.isdir(tmp):
        try:
            os.makedirs(tmp)
        except OSError as e:
            raise CoreError("I/0 Error: " + str(e.strerror), e.filename)


def printSuccessOrFailure(success):
    if success:
        CoreConsole.out(Fore.GREEN + Style.BRIGHT + "SUCCESS" + Fore.RESET + Style.RESET_ALL)
    else:
        CoreConsole.out(Fore.RED + Style.BRIGHT + "FAILURE" + Fore.RESET + Style.RESET_ALL)


def getCoreTypeSize(t):
    sizes = {
        "CHAR": 1, "INT8": 1, "UINT8": 1, "INT16": 2, "UINT16": 2, "INT32": 4, "UINT32": 4, "INT64": 8, "UINT64": 8, "FLOAT32": 4, "FLOAT64": 8, "TIMESTAMP": 8
    }

    return sizes[t]


## https://github.com/ebrehault/superformatter

import string


class SuperFormatter(string.Formatter):
    """World's simplest Template engine."""

    def get_value(self, key, args, kwargs):
        if isinstance(key, int):
            if key not in args:
                return ''
            return args[key]
        else:
            if key not in kwargs:
                return ''
            return kwargs[key]

    def format_field(self, value, spec):
        if spec.startswith('repeat'):
            template = spec.partition(':')[-1]
            if type(value) is dict:
                value = value.items()
            return ''.join([template.format(item=item) for item in value])
        elif spec == 'call':
            return value()
        elif spec.startswith('if'):
            return (value and spec.partition(':')[-1]) or ''
        else:
            return super(SuperFormatter, self).format_field(value, spec)


import io


class CoreReport:
    enabled = True
    debug = True
    verbose = False

    __buffer = None

    FORE_HIGHLIGHT = Fore.YELLOW
    FORE_RESET = Fore.RESET

    def __init__(self):
        self.__buffer = io.StringIO()

    def __str__(self):
        return self.__buffer.getvalue()

    def out(self, message):
        if self.enabled:
            print(message, file=self.__buffer)

    def highlight(self, message):
        return CoreReport.FORE_HIGHLIGHT + message + CoreReport.FORE_RESET

    def highlightFilename(self, filename):
        (p, f) = os.path.split(filename)
        return p + "/" + self.highlight(f)

    @staticmethod
    def success(message):
        return Style.RESET_ALL + Fore.GREEN + Style.BRIGHT + message + Style.RESET_ALL

    @staticmethod
    def fail(message):
        return Style.RESET_ALL + Fore.RED + Style.BRIGHT + message + Style.RESET_ALL

    @staticmethod
    def error(message):
        return Back.RED + Style.BRIGHT + message + Style.RESET_ALL

    @staticmethod
    def warning(message):
        return Back.YELLOW + Style.BRIGHT + message + Style.RESET_ALL

    @staticmethod
    def tableX(data, headers=[], fmt="fancy_grid"):
        return tabulate(data, headers=headers, tablefmt=fmt)

    _invisible_codes = re.compile(r"\x1b\[\d*m|\x1b\[\d*\;\d*\;\d*m")  # Copied from tabulate

    @staticmethod
    def table(data, headers=[], fmt="fancy_grid"):
        tmp = ""
        if len(headers) > 0:
            for x in data:
                for i in range(0, len(x)):
                    tmp += Fore.BLUE + headers[i] + Style.RESET_ALL + ": " + x[i]
                    tmp += "\n"
                tmp += "\n"
        else:
            for x in data:
                for i in range(0, len(x)):
                    tmp += x[i]
                    tmp += "\n"
                tmp += "\n"
        return tmp

    @staticmethod
    def h1(message, w=80):
        visible = re.sub(CoreReport._invisible_codes, "", message)

        tmp = "= " + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL
        tmp += "\n"

        return tmp

    @staticmethod
    def h2(message, w=80):
        tmp = '== ' + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL
        tmp += "\n"
        return tmp

    @staticmethod
    def h3(message, w=80):
        visible = re.sub(CoreReport._invisible_codes, "", message)

        tmp = '------ ' + Fore.BLUE + message + Style.RESET_ALL + ' ' + ('-' * (w - 8 - len(visible)))
        return tmp

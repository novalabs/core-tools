import shutil
from json import loads

from avro.io import validate
from avro.schema import parse

from CoreConsole import *


class Error(Exception):
    """Base class for exceptions in this module."""
    pass


class CoreError(Exception):
    def __init__(self, value, file = None, context = None):
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


def listDirectories(path, fullpath = False):
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


def loadAndValidateJson(filename, schemaJSON):
    schema = parse(schemaJSON)
    try:
        data = loads(open(filename, 'r').read())
        if validate(schema, data):
            return data
        else:
            raise CoreError("File invalid according to schema", filename)
    except ValueError:
        raise CoreError("Broken JSON file", filename)
    except IOError as e:
        raise CoreError("I/0 Error: " + str(e.strerror), e.filename)


def splitFQN(x):
    return x.split("::")


def findFileGoingUp(filename, cwd = None):
    if cwd is None:
        cwd = os.getcwd()

    root = None

    while cwd != "/":
        if os.path.isfile(os.path.join(cwd, filename)):
            root = cwd
            break

        (cwd, t) = os.path.split(cwd)

    return root


def copyOrLink(src, dst, rm = True):
    link = os.environ.get("NOVA_CORE_LINKS_NOT_COPIES")

    if link is not None:
        link = True
    else:
        link = False

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

import git, os, shutil, stat
from CoreUtils import *

class CoreBootstrap:
    schema = '{ "name": "CoreRepos", "type": "record", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "core", "type": { "type": "array", "items": { "type": "record", "name": "CoreReposP", "fields": [ { "name": "name", "type": "string" }, { "name": "url", "type": "string" }, { "name": "branch", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "packages", "type": { "type": "array", "items": { "type": "record", "name": "CoreReposPackageP", "fields": [ { "name": "name", "type": "string" }, { "name": "url", "type": "string" }, { "name": "branch", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "modules", "type": { "type": "array", "items": { "type": "record", "name": "CoreReposModuleP", "fields": [ { "name": "name", "type": "string" }, { "name": "url", "type": "string" }, { "name": "branch", "type": "string" }, { "name": "description", "type": "string" } ] } } } ] }'

    def __init__(self, path):
        self.repos = None
        self.coreRoot = None
        self.source = ""

        self.name = ""
        self.description = ""

        self.core = []
        self.packages = []
        self.modules = []


        self.core = None
        self.repos = None

        self.valid = False

        self.getReposPath(path)

    def getCoreRoot(self, path = ""):
        if self.coreRoot is None:
            self.coreRoot = os.path.join(path, "core")

        return self.coreRoot

    def getReposPath(self, path = ""):
        if self.repos is None:
            self.repos = os.path.join(self.getCoreRoot(path), "repos")

        return self.repos

    def fetchRepo(self, url, branch, path):
        try:
            dst = os.path.join(self.getCoreRoot(), path)

            if os.path.isdir(dst):
                shutil.rmtree(dst)
            else:
                pass

            os.makedirs(dst)
            repo = git.Repo.init(dst)
            origin = repo.create_remote('origin', url)
            origin.fetch()
            repo.git.checkout('origin/' + branch, b=branch)

            return True
        except Exception as e:
            self.reason = str(e)
            return False

    def fetchRepos(self, url = None, path = ""):
        try:
            REMOTE_URL = "https://github.com/novalabs/core-repos.git"

            if os.path.isdir(self.getReposPath()):
                shutil.rmtree(self.getReposPath())

            os.makedirs(self.getReposPath())

            repo = git.Repo.init(self.getReposPath())
            origin = repo.create_remote('origin', REMOTE_URL)
            origin.fetch()
            repo.git.checkout('origin/master', b='master')

            shutil.copy2(os.path.join(self.getReposPath(), "CORE.json"), os.path.join(self.getCoreRoot(), "CORE.json"))

            return True
        except Exception as e:
            self.reason = str(e)
            return False


    def openJSON(self, jsonFile):
        CoreConsole.info("CoreBootstrap: " + CoreConsole.highlightFilename(jsonFile))

        try:
            self.data = loadAndValidateJson(jsonFile, CoreBootstrap.schema)
            self.source = jsonFile
            self.name = self.data["name"]
            self.description = self.data["description"]

            self.valid = True

            return True
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreBootstrap::openJSON: " + self.reason)
            self.valid = False

        return True

    def open(self, path = ""):
        self.valid = False

        try:
            jsonFile = os.path.join(self.getReposPath(path), "REPOS.json")

            return self.openJSON(jsonFile)
        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreBootstrap::open: " + self.reason)
            return False

    def getCore(self):
        if len(x.data["core"]) == 0:
            return None

        return x.data["core"]


    def getModules(self):
        if len(x.data["modules"]) == 0:
            return None

        return x.data["modules"]


    def getPackages(self):
        if len(x.data["packages"]) == 0:
            return None

        return x.data["packages"]

    def writeSetupSh(self):
        buffer = []
        buffer.append('export NOVA_CORE_ROOT=' + self.getCoreRoot())
        buffer.append('export NOVA_CORE_TOOLCHAIN=$NOVA_CORE_ROOT/gcc-arm-none-eabi')
        buffer.append('export NOVA_CHIBIOS_ROOT=$NOVA_CORE_ROOT/chibios')
        buffer.append('export CMAKE_PREFIX_PATH=$NOVA_CORE_ROOT/core-cmake')
        buffer.append('export CMAKE_MODULE_PATH=$NOVA_CORE_ROOT/core-cmake')
        buffer.append('export PATH=$PATH:' + os.path.join(self.getCoreRoot(), 'core-tools'))
        buffer.append('')

        destination = os.path.join(self.getCoreRoot(), "setup.sh")
        sink = open(destination, 'w')
        sink.write("\n".join(buffer))
        os.chmod(destination, 0o744)

        CoreConsole.out(Fore.YELLOW + "setup.sh" + Fore.RESET + " has been generated")

def printElement(x):
    CoreConsole.out(" |- " + Fore.YELLOW + x["name"] + Fore.RESET + ": " + x["description"])
    CoreConsole.out(" |  " + x["url"] + " [" + x["branch"] + "]")


if '__main__' == __name__:
    try:
        CoreConsole.debug = False
        CoreConsole.verbose = False

        x = CoreBootstrap(os.getcwd())

        if not x.fetchRepos():
            raise CoreError(x.reason)

        x.open()

        failure = False
        if True:
            if x.getCore() is not None:
                CoreConsole.out("CORE")
                for tmp in x.getCore():
                    printElement(tmp)
                    if x.fetchRepo(tmp["url"], tmp["branch"], tmp["name"]):
                        CoreConsole.out(" |  " + Fore.GREEN + "Fetched" + Fore.RESET)
                    else:
                        CoreConsole.out(CoreConsole.error(x.reason))
                        failure = True
                CoreConsole.out("")

            if x.getModules() is not None:
                CoreConsole.out("MODULES")
                for tmp in x.getModules():
                    printElement(tmp)
                    if x.fetchRepo(tmp["url"], tmp["branch"], os.path.join("modules", tmp["name"])):
                        CoreConsole.out(" |  " + Fore.GREEN + "Fetched" + Fore.RESET)
                    else:
                        CoreConsole.out(CoreConsole.error(x.reason))
                        failure = True
                CoreConsole.out("")

            if x.getPackages() is not None:
                CoreConsole.out("PACKAGES")
                for tmp in x.getPackages():
                    printElement(tmp)
                    if x.fetchRepo(tmp["url"], tmp["branch"], os.path.join("packages", tmp["name"])):
                        CoreConsole.out(" |  " + Fore.GREEN + "Fetched" + Fore.RESET)
                    else:
                        CoreConsole.out(CoreConsole.error(x.reason))
                        failure = True
                CoreConsole.out("")

        if not failure:
            CoreConsole.out(Fore.GREEN + Style.BRIGHT + "SUCCESS" + Fore.RESET + Style.RESET_ALL)
        else:
            CoreConsole.out(Fore.RED + Style.BRIGHT + "FAILURE" + Fore.RESET + Style.RESET_ALL)
            sys.exit(-1001)

        CoreConsole.out("")

        x.writeSetupSh()



    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1000)
    except Exception as e:
        CoreConsole.out("Exception: " + CoreConsole.error(repr(e)))
        sys.exit(-1000)

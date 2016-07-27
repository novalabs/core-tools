# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import git

from CoreUtils import *
import sys

class CoreBootstrap:
    schema = '{ "name": "CoreRepos", "type": "record", "fields": [ { "name": "name", "type": "string" }, { "name": "description", "type": "string" }, { "name": "core", "type": { "type": "array", "items": { "type": "record", "name": "CoreReposP", "fields": [ { "name": "name", "type": "string" }, { "name": "url", "type": "string" }, { "name": "branch", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "packages", "type": { "type": "array", "items": { "type": "record", "name": "CoreReposPackageP", "fields": [ { "name": "name", "type": "string" }, { "name": "url", "type": "string" }, { "name": "branch", "type": "string" }, { "name": "description", "type": "string" } ] } } }, { "name": "modules", "type": { "type": "array", "items": { "type": "record", "name": "CoreReposModuleP", "fields": [ { "name": "name", "type": "string" }, { "name": "url", "type": "string" }, { "name": "branch", "type": "string" }, { "name": "description", "type": "string" } ] } } } ] }'
    REMOTE_URL = "https://github.com/novalabs/core-repos.git"

    def __init__(self, path):
        self.repos = None
        self.coreRoot = None
        self.source = ""

        self.data = None

        self.name = ""
        self.description = ""

        self.core = []
        self.packages = []
        self.modules = []

        self.core = None
        self.repos = None

        self.valid = False
        self.reason = ""

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

            if os.path.exists(dst):
                repo = git.Repo(dst)
                repo
                if repo.is_dirty(untracked_files=True):
                    return 'dirty'
                else:
                    origin = repo.remotes.origin
                    origin.fetch()
                    repo.heads[branch].checkout()
                    origin.pull(branch)
                    return 'updated'
            else:
                os.makedirs(dst)
                repo = git.Repo.init(dst)
                origin = repo.create_remote('origin', url)
                origin.fetch()
                repo.git.checkout('origin/' + branch, b=branch)
                return 'fetched'
        except Exception as e:
            self.reason = str(e)
            return 'fail'

    def fetchRepos(self, url = None):
        try:
            if url is None:
                url = CoreBootstrap.REMOTE_URL

            if os.path.isdir(self.getReposPath()):
                shutil.rmtree(self.getReposPath())

            os.makedirs(self.getReposPath())

            repo = git.Repo.init(self.getReposPath())
            origin = repo.create_remote('origin', url)
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

        except CoreError as e:
            self.reason = str(e)
            CoreConsole.fail("CoreBootstrap::openJSON: " + self.reason)
            self.valid = False
            return False

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
        if len(bootstrapper.data["core"]) == 0:
            return None

        return bootstrapper.data["core"]

    def getModules(self):
        if len(bootstrapper.data["modules"]) == 0:
            return None

        return bootstrapper.data["modules"]

    def getPackages(self):
        if len(bootstrapper.data["packages"]) == 0:
            return None

        return bootstrapper.data["packages"]

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

        return True


def printElement(x):
    CoreConsole.out(" |- " + Fore.YELLOW + x["name"] + Fore.RESET + ": " + x["description"])
    CoreConsole.out(" |  " + x["url"] + " [" + x["branch"] + "]")

if '__main__' == __name__:
    try:
        CoreConsole.debug = False
        CoreConsole.verbose = False

        CoreConsole.out(Fore.MAGENTA + "Bootstrapping Core Distribution" + Fore.RESET)
        CoreConsole.out("")

        bootstrapper = CoreBootstrap(os.getcwd())

        if not bootstrapper.fetchRepos():
            raise CoreError(bootstrapper.reason)

        bootstrapper.open()

        failure = False

        if bootstrapper.getCore() is not None:
            CoreConsole.out("Fetching CORE")
            for tmp in bootstrapper.getCore():
                printElement(tmp)
                success = bootstrapper.fetchRepo(tmp["url"], tmp["branch"], tmp["name"])
                if success == 'fetched':
                    CoreConsole.out(" |  " + Fore.GREEN + "Fetched" + Fore.RESET)
                if success == 'updated':
                    CoreConsole.out(" |  " + Fore.GREEN + "Updated" + Fore.RESET)
                elif success == 'dirty':
                    CoreConsole.out(" |  " + Fore.RED + "Dirty [skipping]" + Fore.RESET)
                else:
                    CoreConsole.out(CoreConsole.error(bootstrapper.reason))
                    failure = True
            CoreConsole.out("")

        if bootstrapper.getModules() is not None:
            CoreConsole.out("Fetching MODULES")
            for tmp in bootstrapper.getModules():
                printElement(tmp)
                success = bootstrapper.fetchRepo(tmp["url"], tmp["branch"], os.path.join("modules", tmp["name"]))
                if success == 'fetched':
                    CoreConsole.out(" |  " + Fore.GREEN + "Fetched" + Fore.RESET)
                if success == 'updated':
                    CoreConsole.out(" |  " + Fore.GREEN + "Updated" + Fore.RESET)
                elif success == 'dirty':
                    CoreConsole.out(" |  " + Fore.RED + "Dirty [skipping]" + Fore.RESET)
                else:
                    CoreConsole.out(CoreConsole.error(bootstrapper.reason))
                    failure = True
            CoreConsole.out("")

        if bootstrapper.getPackages() is not None:
            CoreConsole.out("Fetching PACKAGES")
            for tmp in bootstrapper.getPackages():
                printElement(tmp)
                success = bootstrapper.fetchRepo(tmp["url"], tmp["branch"], os.path.join("packages", tmp["name"]))
                if success == 'fetched':
                    CoreConsole.out(" |  " + Fore.GREEN + "Fetched" + Fore.RESET)
                if success == 'updated':
                    CoreConsole.out(" |  " + Fore.GREEN + "Updated" + Fore.RESET)
                elif success == 'dirty':
                    CoreConsole.out(" |  " + Fore.RED + "Dirty [skipping]" + Fore.RESET)
                else:
                    CoreConsole.out(CoreConsole.error(bootstrapper.reason))
                    failure = True
            CoreConsole.out("")

        printSuccessOrFailure(not failure)

        if failure:
            sys.exit(-1)

        CoreConsole.out("")

        CoreConsole.out("Generating " + Fore.YELLOW + "setup.sh" + Fore.RESET)
        CoreConsole.out("")

        failure = not bootstrapper.writeSetupSh()

        printSuccessOrFailure(not failure)

        if failure:
            sys.exit(-1)

        sys.exit(0)

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        sys.exit(-1)
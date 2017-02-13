# COPYRIGHT (c) 2016 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import git
import sys

from novalabs.core.CoreBootstrap import *

def printElement(x):
    CoreConsole.out(" |- " + Fore.YELLOW + x["name"] + Fore.RESET + ": " + x["description"])
    CoreConsole.out(" |  " + x["url"] + " [" + x["branch"] + "]")

def fetch(corePath):
    try:
        bootstrapper = CoreBootstrap(corePath)

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
                elif success == 'updated':
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
                elif success == 'updated':
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
                elif success == 'updated':
                    CoreConsole.out(" |  " + Fore.GREEN + "Updated" + Fore.RESET)
                elif success == 'dirty':
                    CoreConsole.out(" |  " + Fore.RED + "Dirty [skipping]" + Fore.RESET)
                else:
                    CoreConsole.out(CoreConsole.error(bootstrapper.reason))
                    failure = True
            CoreConsole.out("")

        if failure:
            return False

        CoreConsole.out("")

        CoreConsole.out("Generating " + Fore.YELLOW + "setup.sh" + Fore.RESET)
        CoreConsole.out("")

        failure = not bootstrapper.writeSetupSh()

        if failure:
            return False

        return True

    except CoreError as e:
        CoreConsole.out(CoreConsole.error(e.value))
        return False


if '__main__' == __name__:
    CoreConsole.debug = False
    CoreConsole.verbose = False

    CoreConsole.out(Fore.MAGENTA + "Bootstrapping Core Distribution" + Fore.RESET)
    CoreConsole.out("")

    isOk = fetch(os.path.join(os.getcwd(), "core"))
    printSuccessOrFailure(isOk)

    if not isOk:
        sys.exit(-1)

    sys.exit(0)


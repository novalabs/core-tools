# COPYRIGHT (c) 2016-2018 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import git
import sys

from novalabs.core.CoreBootstrap import *

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


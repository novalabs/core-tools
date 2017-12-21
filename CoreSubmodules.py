#!/usr/bin/env python3
#  COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import git
import sys

from novalabs.core.Core import *
from novalabs.core.CoreBootstrap import *


if '__main__' == __name__:
    CoreConsole.debug = False
    CoreConsole.verbose = False

    CoreConsole.out(Fore.MAGENTA + "Bootstrapping Core Distribution" + Fore.RESET)
    CoreConsole.out("")

    coreRoot = os.environ.get("NOVA_CORE_ROOT")
    if coreRoot is None:
        CoreConsole.out("NOVA_CORE_ROOT environment variable not found")
        sys.exit(-1)
    src = coreRoot

    isOk = generateSubmodules(coreRoot)
    printSuccessOrFailure(isOk)

    if not isOk:
        sys.exit(-1)

    sys.exit(0)


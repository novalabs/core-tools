# -*- coding: utf-8 -*-

# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import os
import re
from colorama import Fore, Back, Style, init
from tabulate import tabulate

class CoreConsole:
    enabled = True
    debug = True
    verbose = False

    f = None

    FORE_HIGHLIGHT = Fore.YELLOW
    FORE_RESET = Fore.RESET

    init()

    def __init__(self):
        True

    @staticmethod
    def enable():
        CoreConsole.enabled = True

    @staticmethod
    def disable():
        CoreConsole.enabled = False

    @staticmethod
    def enableDebug():
        CoreConsole.debug = True

    @staticmethod
    def disableDebug():
        CoreConsole.debug = False

    @staticmethod
    def info(message):
        if (CoreConsole.enabled & (CoreConsole.debug | CoreConsole.verbose)):
            print("[INFO] " + message, file=CoreConsole.f)

    @staticmethod
    def ok(message):
        if (CoreConsole.enabled & CoreConsole.debug):
            print("[" + Fore.GREEN + " OK " + Style.RESET_ALL + "] " + message, file=CoreConsole.f)

    @staticmethod
    def fail(message):
        if (CoreConsole.enabled & CoreConsole.debug):
            print("[" + Fore.RED + "FAIL" + Style.RESET_ALL + "] " + Back.RED + Style.BRIGHT + message + Style.RESET_ALL, file=CoreConsole.f)

    @staticmethod
    def out(message):
        if (CoreConsole.enabled):
            print(message, file=CoreConsole.f)

    @staticmethod
    def highlight(message):
        return CoreConsole.FORE_HIGHLIGHT + message + CoreConsole.FORE_RESET

    @staticmethod
    def highlightFilename(filename):
        (p, f) = os.path.split(filename)
        return p + "/" + CoreConsole.highlight(f)

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

    _invisible_codes = re.compile(r"\x1b\[\d*m|\x1b\[\d*\;\d*\;\d*m") # Copied from tabulate

    @staticmethod
    def h1X(message, w = 80):
        visible = re.sub(CoreConsole._invisible_codes, "", message)

        tmp = '╒' + ('═' * (w - 2)) + '╕'
        tmp += "\n"
        tmp += '│ ' + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL + (' ' * (w - 3 - len(visible))) +  '│'
        tmp += "\n"
        tmp += '╘' + ('═' * (w - 2)) + '╛'
        return tmp

    @staticmethod
    def h2X(message, w = 80):
        visible = re.sub(CoreConsole._invisible_codes, "", message)

        tmp = '=== ' + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL + ' ' +  ('=' * (w - 5 - len(visible)))
        return tmp

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
        visible = re.sub(CoreConsole._invisible_codes, "", message)

        tmp = "= " + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL
        tmp += "\n"

        return tmp

    @staticmethod
    def h1xx(message, w=80):
        visible = re.sub(CoreConsole._invisible_codes, "", message)

        tmp = '+' + ('-' * (w - 2)) + '+'
        tmp += "\n"
        tmp += '| ' + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL + (' ' * (w - 3 - len(visible))) + '|'
        tmp += "\n"
        tmp += '+' + ('-' * (w - 2)) + '+'
        return tmp


    @staticmethod
    def h2(message, w=80):
        tmp = '== ' + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL
        tmp += "\n"
        return tmp

    @staticmethod
    def h2xx(message, w=80):
        visible = re.sub(CoreConsole._invisible_codes, "", message)
        tmp = "\n"
        tmp += '== ' + Style.BRIGHT + Fore.BLUE + message + Style.RESET_ALL + ' ' + ('=' * (w - 4 - len(visible)))
        tmp += "\n"
        return tmp


    @staticmethod
    def h3(message, w=80):
        visible = re.sub(CoreConsole._invisible_codes, "", message)

        tmp = '------ ' + Fore.BLUE + message + Style.RESET_ALL + ' ' + ('-' * (w - 8 - len(visible)))
        return tmp

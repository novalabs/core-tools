# COPYRIGHT (c) 2016-2017 Nova Labs SRL
#
# All rights reserved. All use of this software and documentation is
# subject to the License Agreement located in the file LICENSE.

import ctypes

TYPE_FORMAT_MAP = {
    "TIMESTAMP": "Q",
    "INT64": "q",
    "UINT64": "Q",
    "FLOAT64": "d",
    "INT32": "l",
    "UINT32": "L",
    "FLOAT32": "f",
    "INT16": "h",
    "UINT16": "H",
    "CHAR": "c",
    "INT8": "b",
    "UINT8": "B"
}

CORE_TYPE_TO_CTYPE_MAP = {
    "TIMESTAMP": ctypes.c_uint64,
    "INT64": ctypes.c_int64,
    "UINT64": ctypes.c_uint64,
    "FLOAT64": ctypes.c_double,
    "INT32": ctypes.c_int32,
    "UINT32": ctypes.c_uint32,
    "FLOAT32": ctypes.c_float,
    "INT16": ctypes.c_int16,
    "UINT16": ctypes.c_uint16,
    "CHAR": ctypes.c_char,
    "INT8": ctypes.c_int8,
    "UINT8": ctypes.c_uint8
}

CORE_TYPE_JSON_DEFINITIONS = {
    "TIMESTAMP": {
        "type": "integer",
        "minimum": 0,
        "maximum": 18446744073709552000
    },
    "INT64": {
        "type": "integer",
        "minimum": -9223372036854776000,
        "maximum": 9223372036854776000
    },
    "UINT64": {
        "type": "integer",
        "minimum": 0,
        "maximum": 18446744073709552000
    },
    "FLOAT64": {
        "type": "number"
    },
    "INT32": {
        "type": "integer",
        "minimum": -2147483648,
        "maximum": 2147483647
    },
    "UINT32": {
        "type": "integer",
        "minimum": 0,
        "maximum": 4294967296
    },
    "FLOAT32": {
        "type": "number"
    },
    "INT16": {
        "type": "integer",
        "minimum": -32768,
        "maximum": 32767
    },
    "UINT16": {
        "type": "integer",
        "minimum": 0,
        "maximum": 65536
    },
    "INT8": {
        "type": "integer",
        "minimum": -128,
        "maximum": 127
    },
    "UINT8": {
        "type": "integer",
        "minimum": 0,
        "maximum": 255
    },
    "CHAR": {
        "type": "string",
        "minLength": 1,
        "maxLength": 1
    }
}


def checkCTypeValueForCoreType(type, size, value):
    values = []
    try:
        if size == 1:
            if isinstance(value, list):
                return None

            if type == "CHAR":
                if not isinstance(value, str):
                    return None
                values.append(value)
            else:
                values.append(value)
        else:
            if type == "CHAR":
                if isinstance(value, str):
                    if len(value) <= size:
                        return [bytes(value, "ascii")]
                return None
            else:
                if len(value) != size:
                    return None

                for x in value:
                    values.append(x)

        success = True
        for x in values:
            success = success and (CORE_TYPE_TO_CTYPE_MAP[type](x).value == x)

        return values
    except TypeError as t:
        return None


def formatValueAsC(type, value):
    if type == "CHAR":
        return "'" + value + "'"
    elif type == "FLOAT32":
        return str(float(value)) + "f"
    elif type == "FLOAT64":
        return str(float(value))
    elif type == "INT8":
        return str(int(value))
    elif type == "UINT8":
        return str(int(value))
    elif type == "INT16":
        return str(int(value))
    elif type == "UINT16":
        return str(int(value))
    elif type == "INT32":
        return str(int(value))
    elif type == "UINT32":
        return str(int(value))
    elif type == "INT64":
        return str(int(value))
    elif type == "UINT64":
        return str(int(value))
    else:
        return str(value)


def formatValuesAsC(type, size, value):
    buffer = ''
    if size == 1:
        buffer = formatValueAsC(type, value)
    else:
        if type == "CHAR":
            buffer = '"' + value + '"'  # str(value).encode("ascii")
        else:
            buffer = "{"
            for x in value:
                buffer = buffer + formatValueAsC(type, x) + ","
            buffer = buffer[:-1]
            buffer = buffer + "}"

    return buffer


def getJSONSchemaElementForCoreType(type, size, useDefinitions=True):
    if type not in TYPE_FORMAT_MAP:
        return None

    tmp = dict()

    try:
        if size == 1:
            if useDefinitions:
                tmp['type'] = '#/definitions/' + type
            else:
                tmp['type'] = CORE_TYPE_JSON_DEFINITIONS[type]
        else:
            if type == "CHAR":
                tmp['type'] = 'string'
                tmp['minLength'] = 1
                tmp['maxLength'] = size
            else:
                tmp['type'] = 'array'
                if useDefinitions:
                    tmp['items'] = '#/definitions/' + type
                else:
                    tmp['items'] = CORE_TYPE_JSON_DEFINITIONS[type]
                tmp['minItems'] = size
                tmp['maxItems'] = size

        return tmp
    except TypeError as t:
        return None

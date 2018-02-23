import io
import queue
import random
import re
import socket
import string
import struct
import time

import serial

import sys, traceback

from novalabs.misc.helpers import *

# from elftools.elf.sections import SymbolTableSection

MODULE_NAME_MAX_LENGTH = 16
NODE_NAME_MAX_LENGTH = 8
TOPIC_NAME_MAX_LENGTH = 16
IHEX_MAX_DATA_LENGTH = 16

APP_THREAD_SYMBOL = 'app_main'
THREAD_PC_OFFSET = 1
APP_CONFIG_SYMBOL = 'app_config'

_MODULE_NAME = ''.join([random.choice(string.ascii_letters + string.digits + '_')
                        for x in range(MODULE_NAME_MAX_LENGTH)])

IDENTIFIER_REGEX_FMT = '^\\w+$'
MODULE_NAME_REGEX_FMT = '^\\w{1,%d}$' % MODULE_NAME_MAX_LENGTH
NODE_NAME_REGEX_FMT = '^\\w{1,%d}$' % NODE_NAME_MAX_LENGTH
TOPIC_NAME_REGEX_FMT = '^\\w{1,%d}$' % TOPIC_NAME_MAX_LENGTH

_id_regex = re.compile(IDENTIFIER_REGEX_FMT)
_module_regex = re.compile(MODULE_NAME_REGEX_FMT)
_node_regex = re.compile(NODE_NAME_REGEX_FMT)
_topic_regex = re.compile(TOPIC_NAME_REGEX_FMT)

CORE_BOOTLOADER_TOPIC_NAME = "BOOTLOADER"
CORE_BOOTLOADER_MASTER_TOPIC_NAME = "BOOTLOADERMSTR"


# ==============================================================================

def _enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    reverse = dict((value, key) for key, value in enums.items())
    enums['_reverse'] = reverse
    return type('Enum', (object,), enums)


def is_identifier(text):
    return bool(_id_regex.match(text))


def is_module_name(text):
    return bool(_module_regex.match(text))


def is_node_name(text):
    return bool(_node_regex.match(text))


def is_topic_name(text):
    return bool(_topic_regex.match(text))


def _get_section_address(elffile, name):
    for section in elffile.iter_sections():
        if section.name == name:
            return section.header['sh_addr']
    raise RuntimeError('Section %s not found' % repr(name))


def _get_function_address(elffile, name):
    dwarfinfo = elffile.get_dwarf_info()
    for CU in dwarfinfo.iter_CUs():
        for DIE in CU.iter_DIEs():
            try:
                if DIE.tag == 'DW_TAG_subprogram' and DIE.attributes['DW_AT_name'].value == name:
                    return int(DIE.attributes['DW_AT_low_pc'].value) + THREAD_PC_OFFSET
            except KeyError:
                continue
    raise RuntimeError('Symbol %s not found' % repr(name))


def _get_symbol_address(elffile, name):
    for section in elffile.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue
        for symbol in section.iter_symbols():
            if symbol.name == name:
                return symbol['st_value']
    raise RuntimeError('Symbol %s not found' % repr(name))


def _get_variable_address(elffile, name):
    dwarfinfo = elffile.get_dwarf_info()
    for CU in dwarfinfo.iter_CUs():
        for DIE in CU.iter_DIEs():
            try:
                if DIE.tag == 'DW_TAG_variable' and DIE.attributes['DW_AT_name'].value == name:
                    value = DIE.attributes['DW_AT_location'].value
                    # FIXME: Handmade address conversion (I don't know how to manage this with pyelftools...)
                    assert value[0] == 3
                    return (value[4] << 24) | (value[3] << 16) | (value[2] << 8) | value[1]
            except KeyError:
                continue
    raise RuntimeError('Symbol %s not found' % repr(name))


def _get_variable_size(elffile, name):
    dwarfinfo = elffile.get_dwarf_info()
    offset = None
    for CU in dwarfinfo.iter_CUs():
        for DIE in CU.iter_DIEs():
            try:
                if DIE.tag == 'DW_TAG_variable' and DIE.attributes['DW_AT_name'].value == name:
                    offset = DIE.attributes['DW_AT_type'].value
                    break
            except KeyError:
                continue
        else:
            continue
        break
    else:
        raise RuntimeError('Symbol %s not found' % repr(name))

    for DIE in CU.iter_DIEs():
        try:
            if DIE.tag == 'DW_TAG_const_type' and DIE.offset == offset:
                offset = DIE.attributes['DW_AT_type'].value
                break
        except KeyError:
            continue
    else:
        pass  # no separate struct/class type definition

    for DIE in CU.iter_DIEs():
        try:
            if DIE.tag == 'DW_TAG_typedef' and DIE.offset == offset:
                offset = DIE.attributes['DW_AT_type'].value
                break
        except KeyError:
            continue
    else:
        pass  # no typedef in C++

    for DIE in CU.iter_DIEs():
        try:
            if DIE.tag == 'DW_TAG_structure_type' and DIE.offset == offset:
                size = DIE.attributes['DW_AT_byte_size'].value
                break
        except KeyError:
            continue
    else:
        raise RuntimeError('Cannot find structure type of variable %s' % repr(name))

    return size


_sys_lock = threading.RLock()


def get_sys_lock():
    global _sys_lock
    return _sys_lock


def ok():
    global _sys_lock
    with _sys_lock:
        return not Middleware.instance().stopped


# ==============================================================================

class Checksummer(object):
    def __init__(self):
        self._accum = 0

    def __int__(self):
        return self.compute_checksum()

    def compute_checksum(self):
        return (0x100 - (self._accum)) & 0xFF

    def add_uint(self, value):
        value = int(value)
        assert value >= 0
        while value > 0:
            self._accum = (self._accum + (value & 0xFF)) & 0xFF
            value >>= 8

    def add_int(self, value, size=4):
        assert size > 0
        self.add_uint(int(value) & ((1 << (8 * size)) - 1))

    def add_bytes(self, chunk):
        for b in chunk:
            self._accum = (self._accum + b) & 0xFF

    def check(self, checksum):
        if checksum != self.compute_checksum():
            raise ValueError('Checksum is 0x%0.2X, expected 0x%0.2X' %
                             (checksum, self.compute_checksum()))


# ==============================================================================

class Serializable(object):
    def __repr(self):
        return str(self.__dict__)

    def marshal(self):
        raise NotImplementedError()
        # return 'data'

    def unmarshal(self, data, offset=0):
        raise NotImplementedError()


# ==============================================================================

class ParserError(Exception):
    def __init__(self, *args, **kwargs):
        super(ParserError, self).__init__(*args, **kwargs)


# ==============================================================================

class TimeoutError(Exception):
    def __init__(self, now=None, deadline=None, start=None, *args, **kwargs):
        super(TimeoutError, self).__init__(*args, **kwargs)
        self.now = now if now is not None else time.time()
        self.deadline = deadline
        self.start = start


# ==============================================================================

class Time(object):
    RAW_MAX = (1 << 31) - 1
    RAW_MIN = -(1 << 31)
    RAW_MASK = (1 << 32) - 1

    def __init__(self, us=0, s=None):
        if s is not None:
            us = s * 1000000
        self.raw = int(us) & self.RAW_MASK

    def __repr__(self):
        assert Time.RAW_MIN <= self.raw <= Time.RAW_MAX
        if self.raw == Time.RAW_MAX:
            return 'Time_INFINITE'
        elif self.raw == Time.RAW_MIN:
            return 'Time_NINFINITE'
        else:
            return 'Time(microseconds=%d, seconds=%f)' % (self.raw, self.to_s())

    def to_us(self):
        return self.raw

    def to_ms(self):
        return self.raw / 1000.0

    def to_s(self):
        return self.raw / 1000000.0

    def to_m(self):
        return self.raw / 60000000.0

    def to_hz(self):
        return 1000000.0 / self.raw

    @staticmethod
    def us(value):
        return Time(value)

    @staticmethod
    def ms(value):
        return Time(float(value) * 1000.0)

    @staticmethod
    def s(value):
        return Time(float(value) * 1000000.0)

    @staticmethod
    def m(value):
        return Time(float(value) * 10000000.0)

    @staticmethod
    def hz(value):
        return Time(60000000.0 / float(value))

    @staticmethod
    def now():
        return Time(time.time() * 1000000)

    def __lt__(self, other):
        return self.raw.__lt__(other.raw)

    def __eq__(self, other):
        return self.raw.__eq__(other.raw)

    def __add__(self, other):
        return Time(self.raw + other.raw)

    def __sub__(self, other):
        return Time(self.raw - other.raw)

    def __iadd__(self, other):
        self.__init__(self.raw + other.raw)
        return self

    def __isub__(self, other):
        self.__init__(self.raw - other.raw)
        return self

    def __int__(self):
        return self.raw

    def __float__(self):
        return self.to_s()


Time_IMMEDIATE = Time(0)
Time_INFINITE = Time(Time.RAW_MAX)
Time_NINFINITE = Time(Time.RAW_MIN)


# ==============================================================================

class MemoryPool(object):
    def __init__(self, type):
        self._type = type
        self._free_queue = queue.LifoQueue()

    def alloc(self):
        item = self._free_queue.get_nowait()
        self._free_queue.task_done()
        return item

    def free(self, item):
        self._free_queue.put_nowait(item)

    def extend(self, length, items=[], ctor_args=(), ctor_kwargs={}):
        length = len(items)
        assert length > 0
        lenitems = len(items)
        assert not lenitems > 0 or lenitems == length

        if lenitems > 0:
            for item in items:
                self.free(item)
        else:
            for i in range(length):
                item = self._type(*ctor_args, **ctor_kwargs)
                self.free(item)


# ==============================================================================

class ArrayQueue(object):
    def __init__(self, length):
        length = int(length)
        assert length > 0
        self.length = length
        self._queue = queue.Queue(length)

    def post(self, item):
        self._queue.put(item)  # DAVIDE nowait

    def fetch(self):
        item = self._queue.get_nowait()
        self._queue.task_done()
        return item


# ==============================================================================

class EventQueue(object):
    def __init__(self):
        self._queue = queue.Queue()

    def signal(self, item=None):
        self._queue.put_nowait(item)

    def wait(self, timeout=Time_INFINITE):
        if timeout == Time_IMMEDIATE:
            item = self._queue.get_nowait()
        elif timeout == Time_INFINITE:
            item = self._queue.get()
        else:
            t = timeout.to_s()
            item = self._queue.get(True, t)
        self._queue.task_done()
        return item


# ==============================================================================

class IhexRecord(Serializable):
    MAX_DATA_LENGTH = 16

    TypeEnum = _enum(
        'DATA',
        'END_OF_FILE',
        'EXTENDED_SEGMENT_ADDRESS',
        'START_SEGMENT_ADDRESS',
        'EXTENDED_LINEAR_ADDRESS',
        'START_LINEAR_ADDRESS'
    )

    def __init__(self, count=0, offset=0, type=None, data='', checksum=0):
        super().__init__()
        self.count = count
        self.offset = offset
        self.type = type
        self.data = data
        self.checksum = checksum

    def __repr__(self):
        return '%s(count=0x%0.2X, offset=0x%0.4X, type=0x%X, data=%s, checksum=0x%0.2X)' % \
               (type(self).__name__, self.count, self.offset, self.type, repr(self.data), self.checksum)

    def __str__(self):
        return ':%0.2X%0.4X%0.2X%s%0.2X' % \
               (self.count, self.offset, self.type, str2hexb(self.data), self.checksum)

    def compute_checksum(self):
        cs = Checksummer()
        cs.add_uint(self.count)
        cs.add_uint(self.offset)
        cs.add_uint(self.type)
        cs.add_bytes(self.data)
        return cs.compute_checksum()

    def check_valid(self):
        if not (0 <= self.count <= 255):
            raise ValueError('not(0 <= count=%d <= 255)' % self.count)
        if self.count != len(self.data):
            raise ValueError('count=%d != len(data)=%d' % (self.count, len(self.data)))
        if not (0 <= self.offset <= 0xFFFF):
            raise ValueError('not(0 <= offset=0x%0.8X <= 0xFFFF)' % self.offset)
        if self.checksum != self.compute_checksum():
            raise ValueError('checksum=%d != expected=%d' % (self.checksum, self.compute_checksum()))

        if self.type == self.TypeEnum.DATA:
            pass
        elif self.type == self.TypeEnum.END_OF_FILE:
            if self.count != 0:
                raise ValueError('count=%s != 0' % self.count)
        elif self.type == self.TypeEnum.EXTENDED_SEGMENT_ADDRESS:
            if self.count != 2:
                raise ValueError('count=%s != 2' % self.count)
            if self.offset != 0:
                raise ValueError('offset=%s != 0' % self.count)
        elif self.type == self.TypeEnum.START_SEGMENT_ADDRESS:
            if self.count != 4:
                raise ValueError('count=%s != 4' % self.count)
            if self.offset != 0:
                raise ValueError('offset=%s != 0' % self.count)
        elif self.type == self.TypeEnum.EXTENDED_LINEAR_ADDRESS:
            if self.count != 2:
                raise ValueError('count=%s != 2' % self.count)
            if self.offset != 0:
                raise ValueError('offset=%s != 0' % self.count)
        elif self.type == self.TypeEnum.START_LINEAR_ADDRESS:
            if self.count != 4:
                raise ValueError('count=%s != 4' % self.count)
            if self.offset != 0:
                raise ValueError('offset=%s != 0' % self.count)
        else:
            raise ValueError('Unknown type %s' % self.type)

    def marshal(self):
        return struct.pack('<BHB%dsB' % self.MAX_DATA_LENGTH,
                           self.count, self.offset, self.type, self.data, self.checksum)

    def unmarshal(self, data, offset=0):
        self.count, self.offset, self.type, data, self.checksum = \
            struct.unpack_from('<BHB%dsB' % self.MAX_DATA_LENGTH, data, offset)
        self.data = data[:self.count]

    def parse_ihex(self, entry):
        if entry[0] != ':':
            raise ValueError("Entry %s does not start with ':'" % repr(entry))
        self.count = int(entry[1:3], 16)
        explen = 1 + 2 * (1 + 2 + 1 + self.count + 1)
        if len(entry) < explen:
            raise ValueError("len(%s) < %d" % (repr(entry), explen))
        self.offset = int(entry[3:7], 16)
        self.type = int(entry[7:9], 16)
        entry = entry[9:]
        self.data = str(bytearray([int(entry[i: (i + 2)], 16) for i in range(0, 2 * self.count, 2)]))
        self.checksum = int(entry[(2 * self.count): (2 * self.count + 2)], 16)
        self.check_valid()
        return self


# ==============================================================================

class Message(Serializable):
    def __init__(self):
        super(Message, self).__init__()
        self._source = None

    def __repr__(self):
        return '%s(_source=%s, _payload_size=0x%0X)' % (type(self).__name__, repr(self._source), self.get_payload_size())

    @staticmethod
    def get_type_size():
        raise NotImplementedError()

    @staticmethod
    def get_payload_size():
        raise NotImplementedError()


# ==============================================================================

class MgmtMsg(Message):
    MAX_PAYLOAD_LENGTH = 31

    TypeEnum = _enum(
        RAW=0x00,

        # Module messages
        ALIVE=0x11,
        STOP=0x12,
        REBOOT=0x13,
        BOOTLOAD=0x14,

        # PubSub messages
        ADVERTISE=0x21,
        SUBSCRIBE_REQUEST=0x22,
        SUBSCRIBE_RESPONSE=0x23,

        # Path messages
        PATH=0x31
    )

    class Path(Serializable):
        def __init__(self, _MgmtMsg, module='', node='', topic=''):
            super(MgmtMsg.Path, self).__init__()
            self._MgmtMsg = _MgmtMsg
            self.module = module
            self.node = node
            self.topic = topic

        def __repr__(self):
            return '%s(MgmtMsg, module=%s, node=%s, topic=%s)' % \
                   (type(self).__name__, repr(self.module), repr(self.node), repr(self.topic))

        def marshal(self):
            lengths = (MODULE_NAME_MAX_LENGTH, NODE_NAME_MAX_LENGTH, TOPIC_NAME_MAX_LENGTH)
            return struct.pack('<%ds%ds%ds' % lengths, self.module, self.node, self.topic)

        def unmarshal(self, data, offset=0):
            lengths = (MODULE_NAME_MAX_LENGTH, NODE_NAME_MAX_LENGTH, TOPIC_NAME_MAX_LENGTH)
            module, node, topic = struct.unpack_from('<%ds%ds%ds' % lengths, data, offset)
            self.module = module.rstrip('\0')
            self.node = node.rstrip('\0')
            self.topic = topic.rstrip('\0')

    class PubSub(Serializable):
        MAX_RAW_PARAMS_LENGTH = 10

        def __init__(self, _MgmtMsg, topic='', payload_size=0, queue_length=0, raw_params=''):
            super(MgmtMsg.PubSub, self).__init__()
            self._MgmtMsg = _MgmtMsg
            self.topic = topic
            self.payload_size = payload_size
            self.queue_length = queue_length
            self.raw_params = raw_params

        def __repr__(self):
            return '%s(MgmtMsg, topic=%s, payload_size=%d, queue_length=%d, raw_params=%s)' % \
                   (type(self).__name__, repr(self.topic), self.payload_size, self.queue_length,
                    repr(self.raw_params.ljust(self.MAX_RAW_PARAMS_LENGTH, '\0')))

        def marshal(self):
            return struct.pack('<%dsHH%ds' % (TOPIC_NAME_MAX_LENGTH, self.MAX_RAW_PARAMS_LENGTH), toBytes(self.topic), self.payload_size, self.queue_length, toBytes(self.raw_params))

        def unmarshal(self, data, offset=0):
            topic, self.payload_size, self.queue_length, raw_params = struct.unpack_from('<%dsHH%ds' % (TOPIC_NAME_MAX_LENGTH, self.MAX_RAW_PARAMS_LENGTH), data, offset)
            self.topic = str(topic).rstrip('\0')
            self.raw_params = str(raw_params).ljust(self.MAX_RAW_PARAMS_LENGTH, "\0")

    class Module(Serializable):

        class Flags(Serializable):
            def __init__(self, intval=0, stopped=None, rebooted=None, boot_mode=None):
                super(MgmtMsg.Module.Flags, self).__init__()
                intval = int(intval)
                self.stopped = bool(stopped if stopped is not None else (intval & (1 << 0)))
                self.rebooted = bool(rebooted if rebooted is not None else (intval & (1 << 1)))
                self.boot_mode = bool(boot_mode if boot_mode is not None else (intval & (1 << 2)))

            def __int__(self):
                return (int(self.stopped) << 0) | \
                       (int(self.rebooted) << 1) | \
                       (int(self.boot_mode) << 2)

            def __repr__(self):
                return '%s(intval=0x%0X, stopped=%d, rebooted=%d, boot_mode=%d)' % \
                       (type(self).__name__, int(self), self.stopped, self.rebooted, self.boot_mode)

            def marshal(self):
                return struct.pack('<B', int(self))

            def unmarshal(self, data, offset=0):
                self.__init__(struct.unpack_from('<B', data, offset))

        def __init__(self, _MgmtMsg, name='', flags=None):
            super(MgmtMsg.Module, self).__init__()
            self._MgmtMsg = _MgmtMsg
            self.name = name
            self.flags = flags if flags is not None else self.Flags()

        def __repr__(self):
            return '%s(MgmtMsg, name=%s, flags=%s)' % (type(self).__name__, repr(self.name), repr(self.flags))

        def marshal(self):
            return struct.pack('<%ds' % MODULE_NAME_MAX_LENGTH, bytes(self.name, encoding="ascii")) + self.flags.marshal()

        def unmarshal(self, data, offset=0):
            name, intflags = struct.unpack_from('<%dsB' % MODULE_NAME_MAX_LENGTH, data, offset)
            self.name = name
            self.flags.__init__(intval=intflags)

    def __init__(self, type=None):
        super(MgmtMsg, self).__init__()
        self.type = type
        self.path = MgmtMsg.Path(self)
        self.pubsub = MgmtMsg.PubSub(self)
        self.module = MgmtMsg.Module(self)

    def __repr__(self):
        typename = type(self).__name__
        t = self.type
        e = MgmtMsg.TypeEnum
        if t in (e.RAW,):
            subtext = ''
        if t in (e.ALIVE, e.STOP, e.REBOOT, e.BOOTLOAD):
            subtext = ', module=%s.%s' % (typename, repr(self.module))
        elif t in (e.ADVERTISE, e.SUBSCRIBE_REQUEST, e.SUBSCRIBE_RESPONSE):
            subtext = ', pubsub=%s.%s' % (typename, repr(self.pubsub))
        else:
            raise ValueError('Unknown management message subtype %d' % self.type)
        return '%s(type=%s.TypeEnum.%s%s)' % (typename, typename, e._reverse[t], subtext)

    @staticmethod
    def get_type_size():
        return MgmtMsg.get_payload_size()

    @staticmethod
    def get_payload_size():
        return MgmtMsg.MAX_PAYLOAD_LENGTH + 1

    def check_type(self, type):
        assert type is not None
        if self.type != type:
            raise ValueError('Unknown management message subtype %d' % type)

    def clean(self, type=None):
        self.__init__()
        self.type = type  # TODO: Build only the needed type

    def marshal(self):
        t = self.type
        e = MgmtMsg.TypeEnum
        if t in (e.RAW,):
            data = ''
        if t in (e.ALIVE, e.STOP, e.REBOOT, e.BOOTLOAD):
            data = self.module.marshal()
        elif t in (e.ADVERTISE, e.SUBSCRIBE_REQUEST, e.SUBSCRIBE_RESPONSE):
            data = self.pubsub.marshal()
        else:
            raise ValueError('Unknown management message subtype %d' % self.type)

        return struct.pack('<%dsB' % self.MAX_PAYLOAD_LENGTH, data, self.type)

    def unmarshal(self, data, offset=0):
        self.clean()
        payload, t = struct.unpack_from('<%dsB' % self.MAX_PAYLOAD_LENGTH, data, offset)
        e = MgmtMsg.TypeEnum
        if t in (e.RAW,):
            pass
        if t in (e.ALIVE, e.STOP, e.REBOOT, e.BOOTLOAD):
            self.module.unmarshal(payload)
        elif t in (e.ADVERTISE, e.SUBSCRIBE_REQUEST, e.SUBSCRIBE_RESPONSE):
            self.pubsub.unmarshal(payload)
        else:
            raise ValueError('Unknown management message subtype %d' % t)
        self.type = t

        # ==============================================================================


class MasterBootMsg(Message):
    MAX_PAYLOAD_LENGTH = 6

    TypeEnum = _enum(
        NONE=0x00,
        REQUEST=0x01,
        MASTER_ADVERTISE=0xA0,
    )

    class ANNOUNCE(Serializable):
        PAYLOAD_LENGTH = 4

        def __init__(self, _MasterBootMsg, uid=None):
            super(MasterBootMsg.ANNOUNCE, self).__init__()
            self._MasterBootMsg = _MasterBootMsg
            self.uid = uid

        def __repr__(self):
            return '%s::[uid=%08X]' % (type(self).__name__, self.uid)

        def marshal(self):
            return struct.pack('<I', self.uid)

        def unmarshal(self, data, offset=0):
            self.uid, = struct.unpack_from('<I', data, offset)

        @staticmethod
        def getUIDFromHexString(hex_string):
            uid = bytes.fromhex(hex_string)
            if len(uid) != 4:
                raise RuntimeError("UID must be 4 bytes long")
            return uid

    class EMPTY(Serializable):
        PAYLOAD_LENGTH = 0

        def __init__(self, _MasterBootMsg):
            super(MasterBootMsg.EMPTY, self).__init__()
            self.MasterBootMsg = _MasterBootMsg

        def __repr__(self):
            return '%s::[]' % (type(self).__name__)

        def marshal(self):
            return bytes()

        def unmarshal(self, data, offset=0):
            pass

    def __init__(self, cmd=TypeEnum.NONE, seq=0xFF):
        # super().__init__() #DAVIDE
        self.cmd = int(cmd)
        self.seq = int(seq)

        self.announce = MasterBootMsg.ANNOUNCE(self)
        self.empty = MasterBootMsg.EMPTY(self)

    def __repr__(self):
        t = self.cmd
        e = MasterBootMsg.TypeEnum
        if t in (e.REQUEST,):
            subtext = repr(self.announce)
            subtype = type(self.announce).__name__
        elif t in (e.MASTER_ADVERTISE,):
            subtext = repr(self.empty)
            subtype = type(self.empty).__name__
        else:
            raise ValueError('Unknown master boot message command %d' % self.cmd)

        return '%s::[cmd=%s seq=%d data=%s]' % (type(self).__name__, e._reverse[t], self.seq, subtext)

    def marshal(self):
        cmd = self.cmd
        e = MasterBootMsg.TypeEnum
        if cmd in (e.REQUEST,):
            data = self.announce.marshal()
            length = self.announce.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.MASTER_ADVERTISE,):
            data = self.empty.marshal()
            length = self.empty.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        else:
            raise ValueError('Unknown master boot message command %d' % self.cmd)

        return struct.pack('<BB%ds%ds' % (length, padding), self.cmd, self.seq, data, toBytes(padding * "\0"))

    def unmarshal(self, data, offset=0):
        self.clean()
        cmd, seq, payload = struct.unpack_from('<BB%ds' % self.MAX_PAYLOAD_LENGTH, data, offset)
        e = MasterBootMsg.TypeEnum
        if cmd in (e.REQUEST,):
            self.announce.unmarshal(payload)
        elif cmd in (e.MASTER_ADVERTISE,):
            self.empty.unmarshal(payload)
        else:
            raise ValueError('Unknown master boot message command %d' % cmd)

        self.cmd = cmd
        self.seq = seq

    def clean(self, type=None):
        self.__init__()
        self.type = type  # TODO: Build only the needed type

    @staticmethod
    def get_type_size():
        return MasterBootMsg.get_payload_size()

    @staticmethod
    def get_payload_size():
        return MasterBootMsg.MAX_PAYLOAD_LENGTH + 2


# ==============================================================================

class BootMsg(Message):
    MAX_PAYLOAD_LENGTH = 46

    TypeEnum = _enum(
        NONE=0x00,
        REQUEST=0x01,
        IDENTIFY_SLAVE=0x02,
        SELECT_SLAVE=0x10,
        DESELECT_SLAVE=0x11,

        ERASE_CONFIGURATION=0x04,
        ERASE_PROGRAM=0x05,
        WRITE_PROGRAM_CRC=0x06,
        ERASE_USER_CONFIGURATION=0x07,

        WRITE_MODULE_NAME=0x27,
        WRITE_MODULE_CAN_ID=0x28,
        DESCRIBE_V1=0x29,
        DESCRIBE_V2=0x26,
        DESCRIBE_V3=0x30,

        TAGS_READ=0x40,

        IHEX_WRITE=0x50,
        IHEX_READ=0x51,

        RESET=0x60,
        BOOTLOAD=0x70,
        BOOTLOAD_BY_NAME=0x71,

        MASTER_ADVERTISE=0xA0,
        MASTER_IGNORE=0xA1,
        MASTER_FORCE=0xA2,

        ACK=0xFF
    )

    class UID(Serializable):
        PAYLOAD_LENGTH = 4

        def __init__(self, _BootMsg, uid=None):
            super(BootMsg.UID, self).__init__()
            self._BootMsg = _BootMsg
            self.uid = uid

        def __repr__(self):
            return '%s::[uid=%08X]' % (type(self).__name__, self.uid)

        def marshal(self):
            return struct.pack('<I', self.uid)

        def unmarshal(self, data, offset=0):
            self.uid, = struct.unpack_from('<I', data, offset)

        @staticmethod
        def getUIDFromHexString(hex_string):
            uid = int(hex_string, 16);
            return uid

    class UIDAndCRC(Serializable):
        PAYLOAD_LENGTH = 4 + 4

        def __init__(self, _BootMsg, uid=None, crc=0):
            super().__init__()
            self._BootMsg = _BootMsg
            self.uid = uid
            self.crc = crc

        def __repr__(self):
            return '%s::[uid=%08X, crc=%08X]' % (type(self).__name__, self.uid, self.crc)

        def marshal(self):
            return struct.pack('<II', self.uid, self.crc)

        def unmarshal(self, data, offset=0):
            self.uid, self.crc = struct.unpack_from('<II', data, offset)

    class UIDAndName(Serializable):
        NAME_LENGTH = 16
        PAYLOAD_LENGTH = 4 + NAME_LENGTH

        def __init__(self, _BootMsg, uid=None, name=''):
            super().__init__()
            self._BootMsg = _BootMsg

            if(len(name) > self.NAME_LENGTH):
                raise Exception()

            self.uid = uid
            self.name = name

        def __repr__(self):
            return '%s::[uid=%08X, name=%s]' % (type(self).__name__, self.uid, self.name)

        def marshal(self):
            return struct.pack('<I%ds' % (self.NAME_LENGTH), self.uid, bytes(self.name, encoding="ascii"))

        def unmarshal(self, data, offset=0):
            self.uid, self.name = struct.unpack_from('<I%ds' % (self.NAME_LENGTH), data, offset)

    class UIDAndID(Serializable):
        PAYLOAD_LENGTH = 4 + 1

        def __init__(self, _BootMsg, uid=None, id=0):
            super().__init__()
            self._BootMsg = _BootMsg

            if(id > 255):
                raise Exception()

            self.uid = uid
            self.id = id

        def __repr__(self):
            return '%s::[uid=%08X, id=%02X]' % (type(self).__name__, self.uid, self.id)

        def marshal(self):
            return struct.pack('<IB', self.uid, self.id)

        def unmarshal(self, data, offset=0):
            self.uid, self.id = struct.unpack_from('<IB', data, offset)

    class UIDAndAddress(Serializable):
        PAYLOAD_LENGTH = 4 + 4

        def __init__(self, _BootMsg, uid=None, address=0):
            super().__init__()
            self._BootMsg = _BootMsg
            self.uid = uid
            self.address = address

        def __repr__(self):
            return '%s::[uid=%08X, address=0x%08X]' % (type(self).__name__, self.uid, self.address)

        def marshal(self):
            return struct.pack('<II', self.uid, self.address)

        def unmarshal(self, data, offset=0):
            self.uid, self.address = struct.unpack_from('<II', data, offset)

    class IHEX(Serializable):
        PAYLOAD_LENGTH = 45

        IHexTypeEnum = _enum(
            BEGIN=0x01,
            DATA=0x02,
            END=0x03
        )

        def __init__(self, _BootMsg, status=IHexTypeEnum.BEGIN, ihex=''):
            super(BootMsg.IHEX, self).__init__()
            self._BootMsg = _BootMsg
            self.type = status
            self.ihex = ihex

        def __repr__(self):
            return '%s::[type=%s, ihex=%s]' % (type(self).__name__, BootMsg.IHEX.IHexTypeEnum._reverse[self.type], self.ihex)

        def marshal(self):
            tmp = toBytes(self.ihex.ljust(44, '\0'))
            return struct.pack('<B%ds' % 44, self.type, tmp)

        def unmarshal(self, data, offset=0):
            self.type, self.ihex = struct.unpack_from('<B%ds' % 44, data, offset)

    class EMPTY(Serializable):
        PAYLOAD_LENGTH = 0

        IHexTypeEnum = _enum(
            BEGIN=0x01,
            DATA=0x02,
            END=0x03
        )

        def __init__(self, _BootMsg):
            super(BootMsg.EMPTY, self).__init__()
            self._BootMsg = _BootMsg

        def __repr__(self):
            return '%s::[]' % (type(self).__name__)

        def marshal(self):
            return bytes()

        def unmarshal(self, data, offset=0):
            pass

    class DESCRIBE_V1(Serializable):
        MODULE_TYPE_LENGTH = 12
        MODULE_NAME_LENGTH = 16
        PAYLOAD_LENGTH = 4 + 2 + 1 + MODULE_TYPE_LENGTH + MODULE_NAME_LENGTH

        def __init__(self, _Acknowledge, program=0, user=0, can_id=0, module_type=None, module_name=None):
            super().__init__()
            self._Acknowledge = _Acknowledge
            self.program = program
            self.user = user
            self.can_id = can_id
            self.module_type = module_type
            self.module_name = module_name

        def __repr__(self):
            return '%s::[program=%d, user=%d, can_id=%02X, type=%s, name=%s]' % (type(self).__name__, self.program, self.user, self.can_id, self.module_type, self.module_name)

        def marshal(self):
            return struct.pack('<IHB%s%s', self.program, self.user, self.can_id, self.module_type, self.module_name)

        def unmarshal(self, data, offset=0):
            self.program, self.user, self.can_id, self.module_type, self.module_name = struct.unpack_from('<IHB%ds%ds' % (self.MODULE_TYPE_LENGTH, self.MODULE_NAME_LENGTH), data, offset)

    class DESCRIBE_V2(Serializable):
        MODULE_TYPE_LENGTH = 12
        MODULE_NAME_LENGTH = 16
        PAYLOAD_LENGTH = 4 + 4 + 4 + 2 + 1 + MODULE_TYPE_LENGTH + MODULE_NAME_LENGTH

        def __init__(self, _Acknowledge, program=0, user=0, can_id=0, module_type=None, module_name=None, conf_crc=0, flash_crc=0):
            super().__init__()
            self._Acknowledge = _Acknowledge
            self.program = program
            self.user = user
            self.can_id = can_id
            self.module_type = module_type
            self.module_name = module_name
            self.confCRC = conf_crc
            self.flashCRC = flash_crc

        def __repr__(self):
            return '%s::[program=%d, user=%d, can_id=%02X, type=%s, name=%s, conf_crc=%d, flash_crc=%d]' % (type(self).__name__, self.program, self.user, self.can_id, self.module_type, self.module_name, self.conf_crc, self.flash_crc)

        def marshal(self):
            return struct.pack('<IIIHB%s%s', self.program, self.conf_crc, self.flash_crc, self.user, self.can_id, self.module_type, self.module_name)

        def unmarshal(self, data, offset=0):
            self.program, self.conf_crc, self.flash_crc, self.user, self.can_id, self.module_type, self.module_name = struct.unpack_from('<IIIHB%ds%ds' % (self.MODULE_TYPE_LENGTH, self.MODULE_NAME_LENGTH), data, offset)

    class DESCRIBE_V3(Serializable):
        MODULE_TYPE_LENGTH = 12
        MODULE_NAME_LENGTH = 16
        PAYLOAD_LENGTH = 4 + 2 + 2 + 1 + 1 + 1 + MODULE_TYPE_LENGTH + MODULE_NAME_LENGTH

        def __init__(self, _Acknowledge, program=0, user=0, tags=0, can_id=0, module_type=None, module_name=None, program_valid=False, user_valid=False):
            super().__init__()
            self._Acknowledge = _Acknowledge
            self.program = program
            self.user = user
            self.tags = tags
            self.can_id = can_id
            self.module_type = module_type
            self.module_name = module_name
            self.program_valid = program_valid
            self.user_valid = user_valid

        def __repr__(self):
            return '%s::[program=%d, user=%d, tags=%d, can_id=%02X, type=%s, name=%s, program_valid=%d, user_valid=%d]' % (type(self).__name__, self.program, self.user, self.tags, self.can_id, self.module_type, self.module_name, self.program_valid, self.user_valid)

        def marshal(self):
            return struct.pack('<IHHBBB%s%s', self.program, self.user, self.tags, self.program_valid, self.user_valid, self.can_id, self.module_type, self.module_name)

        def unmarshal(self, data, offset=0):
            self.program, self.user, self.tags, self.program_valid, self.user_valid, self.can_id, self.module_type, self.module_name = struct.unpack_from('<IHHBBB%ds%ds' % (self.MODULE_TYPE_LENGTH, self.MODULE_NAME_LENGTH), data, offset)

    class Acknowledge(Serializable):
        PAYLOAD_LENGTH = 14

        AckEnum = _enum(
            NONE=0x00,
            OK=0x01,
            WRONG_UID=0x02,
            WRONG_SEQUENCE=0x03,
            DISCARD=0x04,
            NOT_SELECTED=0x05,
            NOT_IMPLEMENTED=0x06,
            BROKEN=0x07,
            ERROR=0x08,
            IHEX_OK=0x09,
            DO_NOT_ACK=0x0A,
            DONE=0x0B
        )

        def __init__(self, _BootMsg, status=AckEnum.NONE, cmd=0x00, uid='', string=''):
            super().__init__()
            self._BootMsg = _BootMsg
            self.cmd = cmd
            self.status = status
            self.uid = BootMsg.UID(self)
            self.string = string
            self.describe_v1 = BootMsg.DESCRIBE_V1(self)
            self.describe_v2 = BootMsg.DESCRIBE_V2(self)
            self.describe_v3 = BootMsg.DESCRIBE_V3(self)

        def __repr__(self):
            t = self.status
            e = BootMsg.TypeEnum
            if self.cmd == e.IHEX_READ:
                return '%s::[status=%s, cmd=%s, data=%s]' % (type(self).__name__, BootMsg.Acknowledge.AckEnum._reverse[self.status], BootMsg.TypeEnum._reverse[self.cmd], self.string)
            elif self.cmd == e.TAGS_READ:
                subtext = self.string
            elif self.cmd == e.DESCRIBE_V1:
                subtext = repr(self.describe_v1)
                subtype = type(self.describe_v1).__name__
            elif self.cmd == e.DESCRIBE_V2:
                subtext = repr(self.describe_v2)
                subtype = type(self.describe_v2).__name__
            elif self.cmd == e.DESCRIBE_V3:
                subtext = repr(self.describe_v3)
                subtype = type(self.describe_v3).__name__
            else:
                subtext = repr(self.uid)
                subtype = type(self.uid).__name__

            return '%s::[status=%s, cmd=%s, data=%s]' % (type(self).__name__, BootMsg.Acknowledge.AckEnum._reverse[self.status], e._reverse[self.cmd], subtext)

        def marshal(self):
            pass

        def unmarshal(self, data, offset=0):
            self.status, self.cmd, payload = struct.unpack_from('<BB%ds' % (BootMsg.MAX_PAYLOAD_LENGTH - 2), data, offset)
            # print(payload)
            e = BootMsg.TypeEnum
            if self.cmd == e.IHEX_READ:
                self.string, = struct.unpack_from('<%ds' % (BootMsg.IHEX.PAYLOAD_LENGTH - 1), payload, 0)
            elif self.cmd == e.TAGS_READ:
                self.string, = struct.unpack_from('<%ds' % (16), payload, 0)
            elif self.cmd == e.DESCRIBE_V1:
                self.describe_v1.unmarshal(payload)
            elif self.cmd == e.DESCRIBE_V2:
                self.describe_v2.unmarshal(payload)
            elif self.cmd == e.DESCRIBE_V3:
                self.describe_v3.unmarshal(payload)
            else:
                self.uid.unmarshal(payload)

    def __init__(self, cmd=TypeEnum.NONE, seq=0xFF):
        # super().__init__() #DAVIDE
        self.cmd = int(cmd)
        self.seq = int(seq)

        self.uid = BootMsg.UID(self)
        self.uid_and_crc = BootMsg.UIDAndCRC(self)
        self.uid_and_name = BootMsg.UIDAndName(self)
        self.uid_and_id = BootMsg.UIDAndID(self)
        self.uid_and_address = BootMsg.UIDAndAddress(self)
        self.ack = BootMsg.Acknowledge(self)
        self.ihex = BootMsg.IHEX(self)
        self.empty = BootMsg.EMPTY(self)

    def __repr__(self):
        t = self.cmd
        e = BootMsg.TypeEnum
        if t in (e.BOOTLOAD,):
            subtext = repr(self.empty)
            subtype = type(self.empty).__name__
        elif t in (e.IDENTIFY_SLAVE, e.SELECT_SLAVE, e.DESELECT_SLAVE, e.ERASE_PROGRAM, e.ERASE_CONFIGURATION, e.ERASE_USER_CONFIGURATION, e.RESET, e.DESCRIBE_V1, e.DESCRIBE_V2, e.DESCRIBE_V3,):
            subtext = repr(self.uid)
            subtype = type(self.uid).__name__
        elif t in (e.WRITE_PROGRAM_CRC,):
            subtext = repr(self.uid_and_crc)
            subtype = type(self.uid_and_crc).__name__
        elif t in (e.WRITE_MODULE_NAME,):
            subtext = repr(self.uid_and_name)
            subtype = type(self.uid_and_name).__name__
        elif t in (e.WRITE_MODULE_CAN_ID,):
            subtext = repr(self.uid_and_id)
            subtype = type(self.uid_and_id).__name__
        elif t in (e.IHEX_READ, e.TAGS_READ,):
            subtext = repr(self.uid_and_address)
            subtype = type(self.uid_and_address).__name__
        elif t in (e.IHEX_WRITE,):
            subtext = repr(self.ihex)
            subtype = type(self.ihex).__name__
        elif t in (e.ACK,):
            subtext = repr(self.ack)
            subtype = type(self.ack).__name__
        else:
            raise ValueError('Unknown boot message command %d' % self.cmd)

        return '%s::[cmd=%s, seq=%d, data=%s]' % (type(self).__name__, e._reverse[t], self.seq, subtext)

    def marshal(self):
        cmd = self.cmd
        e = BootMsg.TypeEnum
        if cmd in (e.REQUEST, e.IDENTIFY_SLAVE, e.SELECT_SLAVE, e.DESELECT_SLAVE, e.ERASE_PROGRAM, e.ERASE_CONFIGURATION, e.ERASE_USER_CONFIGURATION, e.ACK, e.RESET, e.DESCRIBE_V1, e.DESCRIBE_V2, e.DESCRIBE_V3,):
            data = self.uid.marshal()
            length = self.uid.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.IHEX_WRITE,):
            data = self.ihex.marshal()
            length = self.ihex.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.WRITE_PROGRAM_CRC,):
            data = self.uid_and_crc.marshal()
            length = self.uid_and_crc.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.WRITE_MODULE_NAME,):
            data = self.uid_and_name.marshal()
            length = self.uid_and_name.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.WRITE_MODULE_CAN_ID,):
            data = self.uid_and_id.marshal()
            length = self.uid_and_id.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.IHEX_READ, e.TAGS_READ,):
            data = self.uid_and_address.marshal()
            length = self.uid_and_address.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        elif cmd in (e.BOOTLOAD,):
            data = self.empty.marshal()
            length = self.empty.PAYLOAD_LENGTH
            padding = self.MAX_PAYLOAD_LENGTH - length
        else:
            raise ValueError('Unknown boot message command %d' % self.cmd)

        return struct.pack('<BB%ds%ds' % (length, padding), self.cmd, self.seq, data, toBytes(padding * "\0"))

    def unmarshal(self, data, offset=0):
        self.clean()
        cmd, seq, payload = struct.unpack_from('<BB%ds' % self.MAX_PAYLOAD_LENGTH, data, offset)
        e = BootMsg.TypeEnum
        if cmd in (e.IDENTIFY_SLAVE, e.SELECT_SLAVE, e.DESELECT_SLAVE, e.ERASE_PROGRAM, e.ERASE_CONFIGURATION, e.ERASE_USER_CONFIGURATION, e.RESET, e.DESCRIBE_V1, e.DESCRIBE_V2, e.DESCRIBE_V3,):
            self.uid.unmarshal(payload)
        elif cmd in (e.WRITE_PROGRAM_CRC,):
            self.uid_and_crc.unmarshal(payload)
        elif cmd in (e.WRITE_MODULE_NAME,):
            self.uid_and_name.unmarshal(payload)
        elif cmd in (e.WRITE_MODULE_CAN_ID,):
            self.uid_and_id.unmarshal(payload)
        elif cmd in (e.IHEX_READ, e.TAGS_READ,):
            self.uid_and_address.unmarshal(payload)
        elif cmd in (e.IHEX_WRITE,):
            self.ihex.unmarshal(payload)
        elif cmd in (e.ACK,):
            self.ack.unmarshal(payload)
        elif cmd in (e.BOOTLOAD,):
            self.empty.unmarshal(payload)
        else:
            raise ValueError('Unknown boot message command %d' % cmd)

        self.cmd = cmd
        self.seq = seq

    def clean(self, type=None):
        self.__init__()
        self.type = type  # TODO: Build only the needed type

    @staticmethod
    def get_type_size():
        return BootMsg.get_payload_size()

    @staticmethod
    def get_payload_size():
        return BootMsg.MAX_PAYLOAD_LENGTH + 2


# ==============================================================================

class Topic(object):
    def __init__(self, name, msg_type):
        self.name = str(name)
        self.msg_type = msg_type
        self.max_queue_length = 0
        self.publish_timeout = Time_INFINITE

        self.local_publishers = []
        self.local_subscribers = []
        self.remote_publishers = []
        self.remote_subscribers = []

        self._lock = threading.Lock()
        self._msg_pool = MemoryPool(msg_type)

    def __repr__(self):
        return '%s(name=%s, msg_type=%s, max_queue_length=%d, publish_timeout=%s)' % \
               (type(self).__name__, repr(self.name), self.msg_type.__name__, self.max_queue_length, repr(self.publish_timeout))

    def get_type_size(self):
        return self.msg_type.get_type_size()

    def get_payload_size(self):
        return self.msg_type.get_payload_size()

    def get_lock(self):
        return self._lock

    def has_name(self, name):
        return self.name == str(name)

    def has_local_publishers(self):
        return len(self.local_publishers) > 0

    def has_local_subscribers(self):
        return len(self.local_subscribers) > 0

    def has_remote_publishers(self):
        return len(self.remote_publishers) > 0

    def has_remote_subscribers(self):
        return len(self.remote_subscribers) > 0

    def is_awaiting_advertisements(self):
        with self._lock:
            return not self.has_local_publishers() and \
                   not self.has_remote_publishers() and \
                   self.has_local_subscribers()

    def is_awaiting_subscriptions(self):
        with self._lock:
            return not self.has_local_subscribers() and \
                   not self.has_remote_subscribers() and \
                   self.has_local_publishers()

    def alloc(self):
        with self._lock:
            # return self._msg_pool.alloc()
            return self.msg_type()

    def release(self, msg):
        with self._lock:
            # self.free(msg)
            pass

    def free(self, msg):
        with self._lock:
            # self._msg_pool.free(msg)
            pass

    def extend_pool(self, length):
        length = int(length)
        assert length > 0
        with self._lock:
            self._msg_pool.extend([self.msg_type()] * length)

    def notify_locals(self, msg, timestamp):
        with self._lock:
            for sub in self.local_subscribers:
                sub.notify(msg, timestamp)

    def notify_remotes(self, msg, timestamp):
        with self._lock:
            for sub in self.remote_subscribers:
                sub.notify(msg, timestamp)

    def advertise_local(self, pub, publish_timeout):
        with self._lock:
            if self.publish_timeout > publish_timeout:
                self.publish_timeout = publish_timeout
            self.local_publishers.append(pub)

    def advertise_remote(self, pub, publish_timeout):
        with self._lock:
            if self.publish_timeout > publish_timeout:
                self.publish_timeout = publish_timeout
            self.remote_publishers.append(pub)

    def subscribe_local(self, sub):
        with self._lock:
            if self.max_queue_length < sub.get_queue_length():
                self.max_queue_length = sub.get_queue_length()
            self.local_subscribers.append(sub)

    def subscribe_remote(self, sub):
        with self._lock:
            if self.max_queue_length < sub.get_queue_length():
                self.max_queue_length = sub.get_queue_length()
            self.remote_subscribers.append(sub)


# ==============================================================================

class BasePublisher(object):
    def __init__(self):
        self.topic = None
        self._r2p_net_path = '?/?/?'

    def __repr__(self):
        return '<%s(path=%s)>' % (type(self).__name__, repr(self._r2p_net_path))

    def has_topic(self, topic_name):
        return self.topic is not None and self.topic.has_name(topic_name)

    def notify_advertised(self, topic, r2p_net_path=None):
        self.topic = topic
        if r2p_net_path is not None:
            self._r2p_net_path = r2p_net_path
        else:
            self._r2p_net_path = '%s/?/?' % Middleware.instance().module_name

    def alloc(self):
        return self.topic.alloc()

    def publish(self, msg):
        deadline = Time.now() + self.topic.publish_timeout
        locals_done = self.topic.notify_locals(msg, deadline)
        remotes_done = self.topic.notify_remotes(msg, deadline)
        return locals_done and remotes_done

    def publish_locally(self, msg):
        deadline = Time.now() + self.topic.publish_timeout
        return self.topic.notify_locals(msg, deadline)

    def publish_remotely(self, msg):
        deadline = Time.now() + self.topic.publish_timeout
        return self.topic.notify_remotes(msg, deadline)


# ==============================================================================

class BaseSubscriber(object):
    def __init__(self):
        self.topic = None
        self._r2p_net_path = '?/?/?'

    def __repr__(self):
        return '<%s(path=%s)>' % (type(self).__name__, repr(self._r2p_net_path))

    def get_queue_length(self):
        raise NotImplementedError()

    def has_topic(self, topic_name):
        return self.topic is not None and self.topic.has_name(topic_name)

    def notify_subscribed(self, topic, r2p_net_path=None):
        self.topic = topic
        if r2p_net_path is not None:
            self._r2p_net_path = r2p_net_path
        else:
            self._r2p_net_path = '%s/?/?' % Middleware.instance().module_name

    def notify(self, msg, deadline):
        raise NotImplementedError()

    def fetch(self):
        raise NotImplementedError()
        # return (msg, deadline)

    def release(self, msg):
        pass  # gc


# ==============================================================================

class LocalPublisher(BasePublisher):
    def __init__(self):
        super(LocalPublisher, self).__init__()


# ==============================================================================

class LocalSubscriber(BaseSubscriber):
    def __init__(self, queue_length, callback=None):
        super(LocalSubscriber, self).__init__()
        self.queue = ArrayQueue(queue_length)
        self.callback = callback
        self.node = None

    def get_queue_length(self):
        return self.queue.length

    def notify(self, msg, deadline):
        self.queue.post((msg, deadline))
        self.node.notify(self)

    def fetch(self):
        return self.queue.fetch()


# ==============================================================================

class Publisher(LocalPublisher):
    def __init__(self):
        super(Publisher, self).__init__()


# ==============================================================================

class Subscriber(LocalSubscriber):
    def __init__(self, queue_length, callback=None):
        super(Subscriber, self).__init__(queue_length, callback)


# ==============================================================================

class RemotePublisher(BasePublisher):
    def __init__(self, transport):
        super(RemotePublisher, self).__init__()
        self.transport = transport


# ==============================================================================

class RemoteSubscriber(BaseSubscriber):
    def __init__(self, transport):
        super(RemoteSubscriber, self).__init__()
        self.transport = transport


# ==============================================================================

class Node(object):
    def __init__(self, name):
        self.name = str(name)
        self.publishers = []
        self.subscribers = []
        self._publishers_lock = threading.Lock()
        self._subscribers_lock = threading.Lock()
        self.timeout = Time_INFINITE
        self.notification_queue = EventQueue()
        self.stopped = False
        self._stop_lock = threading.RLock()

    def __repr__(self):
        return '%s(name=%s)' % (type(self).__name__, repr(self.name))

    def begin(self):
        logging.debug('Starting %s' % repr(self))
        Middleware.instance().add_node(self)

    def end(self):
        logging.debug('Terminating %s' % repr(self))
        Middleware.instance().confirm_stop(self)

    def advertise(self, pub, topic_name, publish_timeout, msg_type):
        logging.debug('%s advertising %s, msg_type=%s, timeout=%s' % (repr(self), repr(topic_name), msg_type.__name__, repr(publish_timeout)))
        with self._publishers_lock:
            mw = Middleware.instance()
            mw.advertise_local(pub, topic_name, publish_timeout, msg_type)
            pub.node = self
            self.publishers.append(pub)
            pub._r2p_net_path = '%s/%s/%s' % (mw.module_name, self.name, topic_name)

    def subscribe(self, sub, topic_name, msg_type):
        logging.debug('%s subscribing %s, msg_type=%s' % (repr(self), repr(topic_name), msg_type.__name__))
        with self._subscribers_lock:
            mw = Middleware.instance()
            mw.subscribe_local(sub, topic_name, msg_type)
            sub.node = self
            self.subscribers.append(sub)
            sub._r2p_net_path = '%s/%s/%s' % (mw.module_name, self.name, topic_name)

    def notify(self, sub):
        self.notification_queue.signal(sub)

    def notify_stop(self):
        with self._stop_lock:
            if not self.stopped:
                self.stopped = True
                self.notification_queue.signal(None)

    def spin(self, timeout=Time_INFINITE):
        try:
            sub = None
            while sub is None:
                sub = self.notification_queue.wait(timeout)
        except queue.Empty:
            return

        with self._subscribers_lock:
            assert sub in self.subscribers
            msg, timestamp = sub.fetch()
            if sub.callback is not None:
                sub.callback(msg)
            sub.release(msg)


# ==============================================================================

class Transport(object):
    def __init__(self, name):
        assert is_node_name(name)
        self.name = name
        self.publishers = []
        self.subscribers = []
        self._publishers_lock = threading.RLock()
        self._subscribers_lock = threading.RLock()

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def fill_raw_params(self, topic):
        return ''.ljust(MgmtMsg.PubSub.MAX_RAW_PARAMS_LENGTH, '\xAA')

    def touch_publisher(self, topic, raw_params):
        with self._publishers_lock:
            for pub in self.publishers:
                if pub.has_topic(topic.name):
                    return pub
            pub = self._create_publisher(topic, raw_params)
            path = '%s/(%s)/%s' % (Middleware.instance().module_name, self.name, topic.name)
            pub.notify_advertised(topic, path)
            topic.advertise_remote(pub, Time_INFINITE)
            self.publishers.append(pub)
            return pub

    def touch_subscriber(self, topic, queue_length):
        with self._publishers_lock:
            for sub in self.subscribers:
                if sub.has_topic(topic.name):
                    raw_params = self.fill_raw_params(topic)
                    return (sub, raw_params)
            sub, raw_params = self._create_subscriber(topic, queue_length)
            path = '%s/(%s)/%s' % (Middleware.instance().module_name, self.name, topic.name)
            sub.notify_subscribed(topic, path)
            topic.subscribe_remote(sub)
            self.subscribers.append(sub)
            return (sub, raw_params)

    def _advertise_cb(self, topic, raw_params):
        if topic.has_local_subscribers():
            return self.touch_publisher(topic, raw_params)
        return None

    def _subscribe_cb(self, topic, queue_length):
        if topic.has_local_publishers():
            return self.touch_subscriber(topic, queue_length)
        return None

    def advertise(self, pub, topic_name, publish_timeout, msg_type):
        with self._publishers_lock:
            Middleware.instance().advertise_remote(pub, topic_name, publish_timeout, msg_type)
            self.publishers.append(pub)

    def subscribe(self, sub, topic_name, msg_type):
        with self._subscribers_lock:
            Middleware.instance().subscribe_remote(sub, topic_name, msg_type)
            self.subscribers.append(sub)

    def _send_message(self, topic_name, payload):
        raise NotImplementedError()

    def _recv(self):
        raise NotImplementedError()
        # return ('topic', 'payload')

    def _create_publisher(self, topic, raw_params):
        raise NotImplementedError()
        # return XxxPublisher<RemotePublisher>()

    def _create_subscriber(self, topic, queue_length):
        raise NotImplementedError()
        # return XxxSubscriber<RemoteSubscriber>()


# ==============================================================================

_Middleware_instance = None


class Middleware(object):
    MGMT_BUFFER_LENGTH = 5
    MGMT_TIMEOUT_MS = 20

    BOOT_PAGE_LENGTH = 1 << 10
    BOOT_BUFFER_LENGTH = 4

    TOPIC_CHECK_TIMEOUT_MS = 100

    @staticmethod
    def instance():
        global _Middleware_instance
        if _Middleware_instance is not None:
            return _Middleware_instance
        else:
            _Middleware_instance = Middleware(_MODULE_NAME)
            return _Middleware_instance

    def __init__(self, module_name):
        self.module_name = str(module_name)

        assert is_module_name(self.module_name)

        self.topics = []
        self.nodes = []
        self.transports = []

        self._topics_lock = threading.RLock()
        self._nodes_lock = threading.Lock()
        self._transports_lock = threading.Lock()

        self.mgmt_topic = Topic('R2P', MgmtMsg)
        self.mgmt_thread = None
        self.mgmt_pub = Publisher()
        self.mgmt_sub = Subscriber(5, self.mgmt_cb)  # TODO: configure length

        self.boot_topic = Topic(CORE_BOOTLOADER_TOPIC_NAME, BootMsg)
        self.boot_master_topic = Topic(CORE_BOOTLOADER_MASTER_TOPIC_NAME, MasterBootMsg)

        self.stopped = False
        self.num_running_nodes = 0

    def initialize(self, module_name=None):
        if module_name is None:
            module_name = _MODULE_NAME
        self.module_name = str(module_name)
        assert is_module_name(self.module_name)

        logging.info('Initializing middleware %s' % repr(self.module_name))

        self.add_topic(self.boot_topic)
        self.add_topic(self.boot_master_topic)
        self.add_topic(self.mgmt_topic)

        self.mgmt_thread = threading.Thread(name='R2P_MGMT', target=self.mgmt_threadf)
        self.mgmt_thread.start()

        ready = False
        while not ready and ok():
            logging.debug('Awaiting mgmt_topic to be advertised and subscribed')
            with self.mgmt_topic.get_lock():
                ready = self.mgmt_topic.has_local_publishers() and self.mgmt_topic.has_local_subscribers()
            if not ready:
                time.sleep(0.5)  # TODO: configure

    def uninitialize(self):
        logging.info('Uninitializing middleware %s' % repr(self.module_name))
        self.stop()
        pass  # TODO

    def _stop(self):
        global _sys_lock
        with _sys_lock:
            if not self.stopped:
                self.stopped = True

    def stop(self):
        logging.info('Stopping middleware %s' % repr(self.module_name))
        trigger = False
        with _sys_lock:
            if self.stopped:
                return
            self.stopped = True

        running = True
        while running:
            running = False
            with self._nodes_lock:
                for node in self.nodes:
                    node.notify_stop()
                    running = True
            time.sleep(0.5)  # TODO: configure

        self.mgmt_thread.join()

    def stop_remote(self, module_name):
        msg = self.mgmt_pub.alloc()
        msg.clean(MgmtMsg.TypeEnum.STOP)
        msg.module.name = module_name
        self.mgmt_pub.publish_remotely(msg)

    def reboot_remote(self, name, bootload=False):
        if bootload:
            type = MgmtMsg.TypeEnum.BOOTLOAD
        else:
            type = MgmtMsg.TypeEnum.REBOOT

        msg = self.mgmt_pub.alloc()
        msg.clean(type)
        msg.module.name = str(name)
        self.mgmt_pub.publish_remotely(msg)

    def add_node(self, node):
        logging.debug('Adding node %s' % repr(node.name))
        with self._nodes_lock:
            for existing in self.nodes:
                if node is existing or node.name == existing.name:
                    raise KeyError('Node %s already exists' % repr(node.name))
            self.num_running_nodes += 1
            self.nodes.append(node)

    def add_transport(self, transport):
        logging.debug('Adding transport %s' % repr(transport.name))
        with self._transports_lock:
            for existing in self.transports:
                if transport is existing:
                    raise KeyError('Transport already exists')
            self.transports.append(transport)

    def add_topic(self, topic):
        logging.debug('Adding topic %s' % repr(topic.name))
        with self._topics_lock:
            for existing in self.topics:
                if topic is existing or topic.name == existing.name:
                    raise KeyError('Topic %s already exists' % repr(topic.name))
            self.topics.append(topic)

    def advertise_local(self, pub, topic_name, publish_timeout, msg_type):
        with self._topics_lock:
            topic = self.touch_topic(topic_name, msg_type)
            pub.notify_advertised(topic)
            topic.advertise_local(pub, publish_timeout)
            logging.debug('Advertisement of %s by %s' % (repr(topic), repr(pub)))
            try:
                msg = self.mgmt_pub.alloc()
            except queue.Full:
                return
            msg.clean(MgmtMsg.TypeEnum.ADVERTISE)
            msg.pubsub.topic = topic.name
            msg.pubsub.payload_size = topic.get_payload_size()
        self.mgmt_pub.publish_remotely(msg)

    def advertise_remote(self, pub, topic_name, publish_timeout, msg_type):
        with self._topics_lock:
            topic = self.touch_topic(topic_name, msg_type)
            pub.notify_advertised(topic)
            topic.advertise_remote(pub, publish_timeout)
            logging.debug('Advertisement of %s by %s' % (repr(topic), repr(pub)))

    def subscribe_local(self, sub, topic_name, msg_type):
        with self._topics_lock:
            topic = self.touch_topic(topic_name, msg_type)
            sub.notify_subscribed(topic)
            topic.subscribe_local(sub)
            logging.debug('Subscription of %s by %s' % (repr(topic), repr(sub)))
            try:
                msg = self.mgmt_pub.alloc()
            except queue.Full:
                pass
            msg.clean(MgmtMsg.TypeEnum.SUBSCRIBE_REQUEST)
            msg.pubsub.topic = topic.name
            msg.pubsub.payload_size = topic.get_payload_size()
            msg.pubsub.queue_length = topic.max_queue_length
        self.mgmt_pub.publish_remotely(msg)

    def subscribe_remote(self, sub, topic_name, msg_type):
        with self._topics_lock:
            topic = self.touch_topic(topic_name, msg_type)
            sub.notify_subscribed(topic)
            topic.subscribe_remote(sub)
            logging.debug('Subscription of %s by %s' % (repr(topic), repr(sub)))

    def confirm_stop(self, node):
        logging.debug('Node %s halted' % repr(node.name))
        with self._nodes_lock:
            assert self.num_running_nodes > 0
            for existing in self.nodes:
                if node is existing:
                    break
            else:
                raise KeyError('Node %s not registered' % repr(node.name))
            self.num_running_nodes -= 1
            self.nodes = [existing for existing in self.nodes if node is not existing]

    def find_topic(self, topic_name):
        with self._topics_lock:
            for topic in self.topics:
                if topic_name == topic.name:
                    return topic
            return None

    def find_node(self, node_name):
        with self._nodes_lock:
            for node in self.nodes:
                if node_name == node.name:
                    return node
            return None

    def touch_topic(self, topic_name, msg_type):
        with self._topics_lock:
            for topic in self.topics:
                if topic_name == topic.name:
                    return topic

            topic = Topic(topic_name, msg_type)
            self.topics.append(topic)
            return topic

    def mgmt_cb(self, msg):
        if msg.type == MgmtMsg.TypeEnum.ADVERTISE:
            if self.mgmt_pub.topic is None:
                return

            with self._topics_lock:
                topic = self.find_topic(msg.pubsub.topic)
                if topic is None:
                    return

                try:
                    sub_msg = self.mgmt_pub.alloc()
                except queue.Full:
                    return

                sub_msg.clean(MgmtMsg.TypeEnum.SUBSCRIBE_REQUEST)
                sub_msg.pubsub.topic = topic.name
                sub_msg.pubsub.payload_size = topic.get_payload_size()
                sub_msg.pubsub.queue_length = topic.max_queue_length

            self.mgmt_pub.publish_remotely(sub_msg)

        if msg.type == MgmtMsg.TypeEnum.SUBSCRIBE_REQUEST:
            if self.mgmt_pub.topic is None:
                return

            with self._topics_lock:
                topic = self.find_topic(msg.pubsub.topic)
                if topic is None:
                    return

                try:
                    pub_msg = self.mgmt_pub.alloc()
                except queue.Full:
                    return

                pub_msg.clean(MgmtMsg.TypeEnum.SUBSCRIBE_RESPONSE)
                pub_msg.pubsub.topic = topic.name
                pub_msg.pubsub.payload_size = topic.get_payload_size()
            rsub, raw_params = msg._source._subscribe_cb(topic, msg.pubsub.queue_length)
            pub_msg.pubsub.raw_params = raw_params
            self.mgmt_pub.publish_remotely(pub_msg)

        if msg.type == MgmtMsg.TypeEnum.SUBSCRIBE_RESPONSE:
            topic = self.find_topic(msg.pubsub.topic)
            if topic is None:
                return

            rpub = msg._source._advertise_cb(topic, msg.pubsub.raw_params)

    def mgmt_threadf(self):
        node = Node('R2P_MGMT')

        node.begin()
        node.advertise(self.mgmt_pub, 'R2P', Time.ms(200), MgmtMsg)  # TODO: configure
        node.subscribe(self.mgmt_sub, 'R2P', MgmtMsg)  # TODO: configure

        while ok():
            try:
                node.spin(Time.ms(1000))  # TODO: configure
            except TimeoutError:
                pass

        node.end()

    def boot_threadf(self):
        pass  # TODO


# ==============================================================================

class LineIO(object):
    def __init__(self):
        pass

    def open(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def readline(self):
        raise NotImplementedError()
        # return line

    def writeline(self, line):
        raise NotImplementedError()


# ==============================================================================

class SerialLineIO(LineIO):
    def __init__(self, dev_path, baud_rate, newline='\r\n'):
        super(SerialLineIO, self).__init__()
        self._dev_path = str(dev_path)
        self._baud = int(baud_rate)
        self._ser = None
        self._ti = None
        self._to = None
        self._newline = str(newline)
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()

    def __repr__(self):
        return '%s(dev_path=%s, baud_rate=%d)' % (type(self).__name__, repr(self._dev_path), self._baud)

    def open(self):
        if self._ser is None:
            self._ser = serial.Serial(port=self._dev_path, baudrate=self._baud, timeout=0.001)
            self._ti = io.TextIOWrapper(buffer=io.BufferedReader(self._ser, 1),
                                        encoding='ascii', newline=self._newline)
            self._to = io.TextIOWrapper(buffer=io.BufferedWriter(self._ser, buffer_size=128),
                                        encoding='ascii', newline=self._newline)

    def close(self):
        if self._ser is not None:
            self._to.flush()
            self._ser.close()
            self._ser = None
        self._ti = None
        self._to = None

    def readline(self):
        line = ''
        with self._read_lock:
            while True:
                if not ok():
                    raise KeyboardInterrupt('soft interrupt')
                line += str(self._ti.readline())
                if line[-2:] == self._newline:
                    break
        line = line[:-2]
        # XXX logging.debug("%s --->>> %s" % (repr(self._dev_path), repr(line)))
        return line

    def writeline(self, line):
        # XXX logging.debug("%s <<<--- %s" % (repr(self._dev_path), repr(line)))
        with self._write_lock:
            self._to.write(line)
            self._to.write(u'\n')
            self._to.flush()


# ==============================================================================

class StdLineIO(LineIO):
    def __init__(self):
        super(StdLineIO, self).__init__()
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()

    def __repr__(self):
        return type(self).__name__ + '()'

    def open(self):
        pass

    def close(self):
        pass

    def readline(self):
        with self._read_lock:
            line = raw_input()
            logging.debug("stdin --->>> %s" % repr(line))
        return line

    def writeline(self, line):
        with self._write_lock:
            logging.debug("stdout <<<--- %s" % repr(line))
            print(line)


# ==============================================================================

class TCPLineIO(LineIO):
    def __init__(self, address_string, port):
        # super().__init__() #DAVIDE
        self._socket = None
        self._fp = None
        self._address = address_string
        self._port = port

    def __repr__(self):
        return '%s(address_string=%s, port=%d)' % (type(self).__name__, repr(self._address), self._port)

    def open(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((self._address, self._port))
        self._fp = self._socket.makefile()

        time.sleep(1)

    def close(self):
        self._socket.close()
        self._fp = None

    def readline(self):
        line = self._fp.readline().rstrip('\r\n')
        logging.debug("'%s:%d' --->>> %s" % (self._address, self._port, repr(line)))
        return line

    def writeline(self, line):
        logging.debug("'%s:%d' <<<--- %s" % (self._address, self._port, repr(line)))
        self._fp.write(line)
        self._fp.write('\r\n')
        self._fp.flush()


# ==============================================================================

class DebugPublisher(RemotePublisher):
    def __init__(self, transport):
        super(DebugPublisher, self).__init__(transport)


# ==============================================================================

class DebugSubscriber(RemoteSubscriber):
    def __init__(self, transport, queue_length):
        super(DebugSubscriber, self).__init__(transport)
        self.queue = ArrayQueue(queue_length)
        self._lock = threading.Lock()

    def get_queue_length(self):
        with self._lock:
            return self.queue.length

    def notify(self, msg, deadline):
        with self._lock:
            self.queue.post((msg, deadline))
            self.transport._sub_queue.signal(self)

    def fetch(self):
        with self._lock:
            return self.queue.fetch()


# ==============================================================================

class DebugTransport(Transport):
    MGMT_BUFFER_LENGTH = 4
    BOOT_BUFFER_LENGTH = 5

    class MsgParser(object):
        def __init__(self, line):
            self._line = str(line)
            self._linelen = len(self._line)
            self._offset = 0

        def _check_length(self, length):
            assert length >= 0
            endx = self._offset + length
            if self._linelen < endx:
                raise ParserError("Expected %d chars at %s[%d:%d] == %s (%d chars less)" %
                                  (length, repr(self._line), self._offset, endx,
                                   repr(self._line[self._offset: endx]), endx - self._linelen))

        def check_eol(self):
            assert self._linelen >= self._offset
            if self._linelen > self._offset:
                raise ParserError("Expected end of line at %s[%d:] == %s (%d chars more)" %
                                  (repr(self._line), self._offset, repr(self._line[self._offset:]),
                                   self._linelen - self._offset))

        def expect_char(self, c):
            self._check_length(1)
            if self._line[self._offset] != c:
                raise ParserError("Expected %s at %s[%d] == %s" %
                                  (repr(c), repr(self._line), self._offset, repr(self._line[self._offset])))
            self._offset += 1

        def read_char(self):
            self._check_length(1)
            c = self._line[self._offset]
            self._offset += 1
            return c

        def skip_after_char(self, c):
            try:
                while self.read_char() != c:
                    pass
            except ParserError:
                raise ParserError("Expected %s in %s" % (repr(c), repr(self._line)))

        def read_hexb(self):
            self._check_length(2)
            off = self._offset
            try:
                b = int(self._line[off: off + 2], 16)
            except:
                raise ParserError("Expected hex byte at %s[%d:%d] == %s" %
                                  (repr(self._line), off, off + 2, repr(self._line[off: off + 2])))
            self._offset += 2
            return b

        def read_unsigned(self, size):
            assert size > 0
            self._check_length(2 * size)
            value = 0
            while size > 0:
                value = (value << 8) | self.read_hexb()
                size -= 1
            return value

        def read_string(self, length):
            self._check_length(length)
            s = self._line[self._offset: self._offset + length]
            self._offset += length
            return s

        def read_bytes(self, length):
            self._check_length(2 * length)
            tmp = bytearray([self.read_unsigned(1) for i in range(length)])
            return tmp

    def __init__(self, name, lineio):
        super(DebugTransport, self).__init__(name)
        self._lineio = lineio
        self._rx_thread = None
        self._tx_thread = None
        self._mgmt_rpub = DebugPublisher(self)
        self._mgmt_rsub = DebugSubscriber(self, self.MGMT_BUFFER_LENGTH)
        self._boot_rpub = DebugPublisher(self)
        self._boot_rsub = DebugSubscriber(self, self.BOOT_BUFFER_LENGTH)
        self._boot_master_rpub = DebugPublisher(self)
        self._boot_master_rsub = DebugSubscriber(self, self.BOOT_BUFFER_LENGTH)
        self._sub_queue = EventQueue()
        self._running = False
        self._running_lock = threading.Lock()

    def __repr__(self):
        return '%s(name=%s, lineio=%s)' % (type(self).__name__, repr(self.name), repr(self._lineio))

    def open(self):
        with self._running_lock:
            if not self._running:
                logging.info('Opening %s' % repr(self))
                self._running = True
                self._lineio.open()
                self._lineio.writeline('')
                self._lineio.writeline('')
                self._lineio.writeline('')
                self._rx_thread = threading.Thread(name=(self.name + '_RX'), target=self._rx_threadf)
                self._tx_thread = threading.Thread(name=(self.name + '_TX'), target=self._tx_threadf)
                self._rx_thread.start()
                self._tx_thread.start()
                self.advertise(self._mgmt_rpub, 'R2P', Time.ms(200), MgmtMsg)  # TODO: configure
                self.subscribe(self._mgmt_rsub, 'R2P', MgmtMsg)  # TODO: configure
                self.advertise(self._boot_master_rpub, CORE_BOOTLOADER_MASTER_TOPIC_NAME, Time.ms(200), MasterBootMsg)  # TODO: configure
                self.subscribe(self._boot_master_rsub, CORE_BOOTLOADER_MASTER_TOPIC_NAME, MasterBootMsg)  # TODO: configure
                self.advertise(self._boot_rpub, CORE_BOOTLOADER_TOPIC_NAME, Time.ms(200), BootMsg)  # TODO: configure
                self.subscribe(self._boot_rsub, CORE_BOOTLOADER_TOPIC_NAME, BootMsg)  # TODO: configure
                logging.info('%s open' % repr(self))
                Middleware.instance().add_transport(self)
            else:
                raise RuntimeError('%s already open' % repr(self))

    def close(self):
        with self._running_lock:
            if self._running:
                logging.info('Closing %s' % repr(self))
                self._running = False
            else:
                raise RuntimeError('%s already closed' % repr(self))

        self._rx_thread.join()
        self._rx_thread = None

        self._sub_queue.signal(None)
        self._tx_thread.join()
        self._tx_thread = None

        self._lineio.close()
        logging.info('%s closed' % repr(self))

    def _send_message(self, topic_name, payload):
        assert is_topic_name(topic_name)
        assert len(payload) < 256
        now_raw = Time.now().raw
        cs = Checksummer()
        cs.add_uint(now_raw)
        cs.add_uint(len(topic_name))
        cs.add_bytes(toBytes(topic_name))
        cs.add_uint(len(payload))
        cs.add_bytes(payload)
        args = (now_raw, len(topic_name), topic_name,
                len(payload), str2hexb(payload),
                cs.compute_checksum())
        line = '@%.8X:%.2X%s:%.2X%s:%0.2X' % args
        if topic_name == CORE_BOOTLOADER_TOPIC_NAME:
            #### print("<<< " + line) # DAVIDE
            pass
        if topic_name == CORE_BOOTLOADER_MASTER_TOPIC_NAME:
            #### print("<<< " + line)  # DAVIDE
            pass
        self._lineio.writeline(line)

    def _recv(self):
        cs = Checksummer()
        while True:
            with self._running_lock:
                if not self._running:
                    return None

            # Start parsing the incoming message
            line = self._lineio.readline()
            parser = self.MsgParser(line)
            parser.skip_after_char('@')
            break

        ####print(">>> " + line) # DAVIDE

        deadline = parser.read_unsigned(4)
        cs.add_uint(deadline)
        deadline = Time.us(deadline)

        parser.expect_char(':')
        length = parser.read_unsigned(1)
        if length == 0:
            raise ValueError('length == 0')
        topic = parser.read_string(length)
        cs.add_uint(length)
        cs.add_bytes(toBytes(topic))

        parser.expect_char(':')
        length = parser.read_unsigned(1)
        payload = parser.read_bytes(length)
        cs.add_uint(length)
        cs.add_bytes(payload)

        parser.expect_char(':')
        checksum = parser.read_unsigned(1)
        cs.check(checksum)

        parser.check_eol()
        return (topic, payload)

    def _create_publisher(self, topic, raw_params):
        rpub = DebugPublisher(self)
        return rpub

    def _create_subscriber(self, topic, queue_length):
        rsub = DebugSubscriber(self, queue_length)
        raw_params = self.fill_raw_params(topic)
        return (rsub, raw_params)

    def _is_running(self):
        with self._running_lock:
            return self._running

    def _rx_threadf(self):
        try:
            while self._is_running():
                try:
                    topic_name, payload = self._recv()
                except (ParserError, ValueError) as e:
                    logging.debug(str(e))
                    continue

                topic = Middleware.instance().find_topic(topic_name)
                if topic is None:
                    continue

                with self._publishers_lock:
                    for rpub in self.publishers:
                        if rpub.topic is topic:
                            break
                    else:
                        continue
                try:
                    msg = rpub.alloc()
                    msg.unmarshal(payload)
                    msg._source = self
                    x = repr(msg)
                    logging.debug('--->>> %s' % x)
                    rpub.publish_locally(msg)

                except queue.Full:
                    logging.warning('Full %s' % repr(rpub))
                    pass

                except Exception as e:  # suppress errors
                    print(repr(e))
                    topic.release(msg)  # TODO: Create BasePublisher.release() like BaseSubscriber.release()
                    logging.warning(e)

        except KeyboardInterrupt:
            logging.debug('_rx_threadf interrupted manually')

        except Exception as e:
            logging.exception(e)
            raise

    def _tx_threadf(self):
        try:
            while self._is_running():
                try:
                    sub = self._sub_queue.wait()
                except TimeoutError:
                    continue
                if sub is None:
                    continue

                msg, deadline = sub.fetch()
                try:
                    logging.debug('<<<--- %s' % repr(msg))
                    self._send_message(sub.topic.name, msg.marshal())
                finally:
                    sub.release(msg)

        except KeyboardInterrupt:
            logging.debug('_tx_threadf interrupted manually')

        except Exception as e:
            logging.exception(e)
            raise


# ==============================================================================

class Bootloader(object):
    States = _enum(
        IDLE=0x00,

        IDENTIFYING=0x02,

        SELECTING=0x10,
        SELECTED=0x11,
        DESELECTING=0x12,

        NONE=0xFF
    )

    Errors = _enum(
        SUCCESS=0x00,
        WRONG_SEQUENCE=0x01,
        NONE=0xFF
    )

    def __init__(self):
        self.target_uid = None
        self.sel_desel = True

        self._lock = threading.Lock()
        self._runner = None
        self._mustRun = False
        self._state = Bootloader.States.NONE
        self._slaves = {}
        self._slavesNames = {}
        self._slavesTypes = {}
        self._slavesUserStorageSize = {}
        self._slavesProgramStorageSize = {}
        self._lastSeq = 0

        self._lastAck = BootMsg.Acknowledge(None)
        self._rx_queue = queue.Queue()
        self._tx_queue = queue.Queue()

        self._subShort = None
        self._sub = None
        self._pub = None

    def _callbackShort(self, msg):
        #logging.debug('BOOTLOADER >>> %s' % repr(self))
        #### print(repr(msg)) ####


        if msg.cmd == MasterBootMsg.TypeEnum.REQUEST:
            if msg.announce.uid in self._slaves:
                self._slaves[msg.announce.uid] += 1
            else:
                self._slaves[msg.announce.uid] = 1

            return

    def _callback(self, msg):
        # logging.debug('BOOTLOADER >>> %s' % repr(self))
        #### print(repr(msg)) ####

        if msg.cmd == BootMsg.TypeEnum.ACK:
            self._rx_queue.put_nowait(msg)

            return

    def _rx(self, timeout=0.25):
        try:
            if timeout is not None:
                return self._rx_queue.get(True, timeout)
            else:
                return self._rx_queue.get_nowait()
        except queue.Empty:
            return None

    def _tx(self, msg):
        self._tx_queue.put(msg)  # NOWAIT DAVIDE

    def _node(self, mw, transport):
        node = Node('bl_node')
        node.begin()

        node.subscribe(self._subShort, CORE_BOOTLOADER_MASTER_TOPIC_NAME, MasterBootMsg)
        node.subscribe(self._sub, CORE_BOOTLOADER_TOPIC_NAME, BootMsg)
        node.advertise(self._pub, CORE_BOOTLOADER_TOPIC_NAME, Time(Time.RAW_MAX), BootMsg)

        self._state = Bootloader.States.IDLE

        while ok() and self._mustRun:
            node.spin(Time.ms(0.1))
            try:
                # msg = self._tx_queue.get(True, float(0.05))
                msg = self._tx_queue.get_nowait()
            except queue.Empty:
                msg = None

            if msg is not None:
                self._pub.publish(msg)

        node.end()

        self._state = Bootloader.States.NONE

    def start(self):
        if self._runner is None:
            if self._subShort is None:
                self._subShort = LocalSubscriber(10, self._callbackShort)
            if self._sub is None:
                self._sub = LocalSubscriber(10, self._callback)
            if self._pub is None:
                self._pub = Publisher()

            self._runner = threading.Thread(name='blsub', target=self._node, args=(None, None))
            self._mustRun = True
            self._runner.start()

    def stop(self):
        if self._runner is not None:
            self._mustRun = False
            self._runner.join()

    def clear(self):
        with self._lock:
            self._slaves.clear()
            self._slavesTypes.clear()
            self._slavesNames.clear()
            self._slavesUserStorageSize.clear()
            self._slavesProgramStorageSize.clear()

    def getSlaves(self):
        return self._slaves.keys()

    def getSlavesProgramStorageSize(self, uid):
        if uid in self.getSlaves():
            return self._slavesProgramStorageSize[uid]

        return None

    def _emptyShortCommandNoAck(self, cmd):
        m = MasterBootMsg(cmd, 0)
        m.uid = MasterBootMsg.EMPTY(m)

        #####print(repr(m))

        self._tx(m)
        return True

    def _emptyCommand(self, cmd, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid = BootMsg.EMPTY(m)

        #####print(repr(m))

        self._tx(m)
        # time.sleep(1)
        if self.waitForAck(m) == BootMsg.Acknowledge.AckEnum.OK:
            return True
        else:
            print()
            return False

    def _emptyCommandNoAck(self, cmd):
        m = BootMsg(cmd, 0)
        m.uid = BootMsg.EMPTY(m)

        #####print(repr(m))

        self._tx(m)
        return True

    def _uidCommand(self, cmd, uid, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid = BootMsg.UID(m, uid)

        #####print(repr(m))

        self._tx(m)
        # time.sleep(1)
        if self.waitForAck(m) == BootMsg.Acknowledge.AckEnum.OK:
            return True
        else:
            print()
            return False

    def _uidAndNameCommand(self, cmd, uid, name, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid_and_name = BootMsg.UIDAndName(m, uid, name)

        #####print(repr(m))

        self._tx(m)
        # time.sleep(1)
        if self.waitForAck(m) == BootMsg.Acknowledge.AckEnum.OK:
            return True
        else:
            print()
            return False

    def _uidAndCrcCommand(self, cmd, uid, crc, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid_and_crc = BootMsg.UIDAndCRC(m, uid, crc)

        #####print(repr(m))

        self._tx(m)
        # time.sleep(1)
        if self.waitForAck(m) == BootMsg.Acknowledge.AckEnum.OK:
            return True
        else:
            print()
            return False

    def _uidAndIdCommand(self, cmd, uid, id, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid_and_id = BootMsg.UIDAndID(m, uid, id)

        #####print(repr(m))

        self._tx(m)
        # time.sleep(1)
        if self.waitForAck(m) == BootMsg.Acknowledge.AckEnum.OK:
            return True
        else:
            print()
            return False

    def _uidAndAddressCommand(self, cmd, uid, address, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid_and_address = BootMsg.UIDAndAddress(m, uid, address)

        #####print(repr(m))

        self._tx(m)
        # time.sleep(1)
        if self.waitForAck(m) == BootMsg.Acknowledge.AckEnum.OK:
            return True
        else:
            print()
            return False

    def _ihexWriteCommand(self, cmd, type, ihex, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            ###            self._lastSeq = seq
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.ihex = BootMsg.IHEX(m, type, ihex)

        self._tx(m)
        # time.sleep(0.25)

        ###        seq = self._lastSeq + 1
        ###        self._lastSeq = seq
        ###        if seq == 256:
        ###            seq = 0

        ###        msg = self._rx(None)
        ###        if msg is not None:
        ###self._lastSeq = m.seq + 1
        ### if self._lastSeq == 256:
        ###     self._lastSeq = 0
        ### if msg.ack.status != BootMsg.Acknowledge.AckEnum.OK:
        ###     return False

        ### return True
        if self.waitForAck(m, 15) == BootMsg.Acknowledge.AckEnum.OK:  # DIOBONO
            return True
        else:
            return False

    def _ihexReadCommand(self, cmd, uid, address, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid_and_address = BootMsg.UIDAndAddress(m, uid, address)

        #####print(repr(m))

        self._tx(m)

        return self.waitForStringAck(m)

    def _describeV1Command(self, cmd, uid, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid = BootMsg.UID(m, uid)

        #####print(repr(m))

        self._tx(m)

        status, description = self.waitForDescribeV1Ack(m)

        if status == BootMsg.Acknowledge.AckEnum.OK:
            return description
        else:
            return None

    def _describeV2Command(self, cmd, uid, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid = BootMsg.UID(m, uid)

        #####print(repr(m))

        self._tx(m)

        status, description = self.waitForDescribeV2Ack(m)

        if status == BootMsg.Acknowledge.AckEnum.OK:
            return description
        else:
            return None

    def _describeV3Command(self, cmd, uid, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid = BootMsg.UID(m, uid)

        #####print(repr(m))

        self._tx(m)

        status, description = self.waitForDescribeV3Ack(m)

        if status is not None:
            if status == BootMsg.Acknowledge.AckEnum.OK:
                return description

        return None

    def _tagsReadCommand(self, cmd, uid, address, seq=None):
        if seq is None:
            seq = self._lastSeq + 1
            if seq == 256:
                seq = 0

        m = BootMsg(cmd, seq)
        m.uid_and_address = BootMsg.UIDAndAddress(m, uid, address)

        #####print(repr(m))

        self._tx(m)

        return self.waitForTagsAck(m)

    def bootload(self):
        return self._emptyCommandNoAck(BootMsg.TypeEnum.BOOTLOAD)

    def identify(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.IDENTIFY_SLAVE, uid, 0)

    def select(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.SELECT_SLAVE, uid, 0)

    def deselect(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.DESELECT_SLAVE, uid)

    def eraseProgram(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.ERASE_PROGRAM, uid)

    def eraseConfiguration(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.ERASE_CONFIGURATION, uid)

    def eraseUserConfiguration(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.ERASE_USER_CONFIGURATION, uid)

    def reset(self, uid):
        return self._uidCommand(BootMsg.TypeEnum.RESET, uid)

    def ihex_write(self, type, ihex):
        return self._ihexWriteCommand(BootMsg.TypeEnum.IHEX_WRITE, type, ihex)

    def ihex_read(self, uid, address):
        status = self._ihexReadCommand(BootMsg.TypeEnum.IHEX_READ, uid, address)
        while status == BootMsg.Acknowledge.AckEnum.IHEX_OK:
            status = self._ihexReadCommand(BootMsg.TypeEnum.IHEX_READ, uid, 0xFFFFFFFF)

        return status == BootMsg.Acknowledge.AckEnum.OK

    def write_name(self, uid, name):
        return self._uidAndNameCommand(BootMsg.TypeEnum.WRITE_MODULE_NAME, uid, name)

    def write_program_crc(self, uid, crc):
        return self._uidAndCrcCommand(BootMsg.TypeEnum.WRITE_PROGRAM_CRC, uid, crc)

    def write_id(self, uid, id):
        return self._uidAndIdCommand(BootMsg.TypeEnum.WRITE_MODULE_CAN_ID, uid, id)

    def describe_v1(self, uid):
        return self._describeV1Command(BootMsg.TypeEnum.DESCRIBE_V1, uid)

    def describe_v2(self, uid):
        return self._describeV2Command(BootMsg.TypeEnum.DESCRIBE_V2, uid)

    def describe_v3(self, uid):
        return self._describeV3Command(BootMsg.TypeEnum.DESCRIBE_V3, uid)

    def tags_read(self, uid, address):
        data = bytearray()
        status, tmp = self._tagsReadCommand(BootMsg.TypeEnum.TAGS_READ, uid, 0)
        data.extend(tmp)
        while status == BootMsg.Acknowledge.AckEnum.OK:
            status, tmp = self._tagsReadCommand(BootMsg.TypeEnum.TAGS_READ, uid, 0xFFFFFFFF)
            data.extend(tmp)

        if status == BootMsg.Acknowledge.AckEnum.DONE:
            return data
        else:
            return None

    def waitForAck(self, m, timeout=5.0):
        msg = self._rx(timeout)
        while msg is not None:
            if msg.seq == m.seq + 1:
                if msg.ack.cmd == m.cmd:
                    self._lastSeq = m.seq + 1
                    if self._lastSeq == 256:
                        self._lastSeq = 0
                    return msg.ack.status
            msg = self._rx(timeout)

        return None

    def waitForStringAck(self, m, timeout=5.0):
        msg = self._rx(timeout)
        while msg is not None:
            if msg.seq == m.seq + 1:
                if msg.ack.cmd == m.cmd:
                    self._lastSeq = m.seq + 1
                    if self._lastSeq == 256:
                        self._lastSeq = 0
                    return msg.ack.status, msg.ack.string
            msg = self._rx(timeout)

        return None

    def waitForTagsAck(self, m, timeout=5.0):
        msg = self._rx(timeout)
        while msg is not None:
            if msg.seq == m.seq + 1:
                if msg.ack.cmd == m.cmd:
                    self._lastSeq = m.seq + 1
                    if self._lastSeq == 256:
                        self._lastSeq = 0
                    return msg.ack.status, msg.ack.string
            msg = self._rx(timeout)

        return None

    def waitForDescribeV1Ack(self, m, timeout=5.0):
        msg = self._rx(timeout)
        while msg is not None:
            if msg.seq == m.seq + 1:
                if msg.ack.cmd == m.cmd:
                    self._lastSeq = m.seq + 1
                    if self._lastSeq == 256:
                        self._lastSeq = 0
                    return msg.ack.status, msg.ack.describe_v1
            msg = self._rx(timeout)

        return None, None

    def waitForDescribeV2Ack(self, m, timeout=5.0):
        msg = self._rx(timeout)
        while msg is not None:
            if msg.seq == m.seq + 1:
                if msg.ack.cmd == m.cmd:
                    self._lastSeq = m.seq + 1
                    if self._lastSeq == 256:
                        self._lastSeq = 0
                    return msg.ack.status, msg.ack.describe_v2
            msg = self._rx(timeout)

        return None, None

    def waitForDescribeV3Ack(self, m, timeout=5.0):
        msg = self._rx(timeout)
        while msg is not None:
            if msg.seq == m.seq + 1:
                if msg.ack.cmd == m.cmd:
                    self._lastSeq = m.seq + 1
                    if self._lastSeq == 256:
                        self._lastSeq = 0
                    return msg.ack.status, msg.ack.describe_v3
            msg = self._rx(timeout)

        return None, None

    def pollForAck(self, m, timeout=2.0):
        deadline = Time.now() + Time.s(timeout)
        while Time.now() < deadline:
            time.sleep(0.001)
            msg = self._rx(None)
            if msg is not None:
                # print(repr(msg))
                if msg.seq == m.seq + 1:
                    if msg.ack.cmd == m.cmd:
                        self._lastSeq = m.seq + 1
                        if self._lastSeq == 256:
                            self._lastSeq = 0
                        return msg.ack.status

        return None

# ==============================================================================

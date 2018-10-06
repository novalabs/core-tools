from collections import namedtuple
import sys

FWU = namedtuple('FWU', ['crc', 'dest_filename', 'revision', 'match_type', 'match_name', 'match_uid', 'write_name', 'write_id', 'config', 'program', 'program_crc'])

def fwu_parse(filename):
    crc = None
    dest_filename = None
    revision = None
    match_type = None
    match_name = None
    match_uid = None
    write_name = None
    write_id = None
    config = ""
    program = ""
    program_crc = None

    is_reading_program = False
    is_reading_config = False

    with open (filename, 'rt') as fwu_file:
        for line in fwu_file:
            if is_reading_config and line.startswith(':'):
                config += line
                continue
            if is_reading_program and line.startswith(':'):
                program += line
                continue

            if line.startswith('@CRC'):
                crc = int(line[5:].strip(), 16)
            elif line.startswith('!DEST_FILENAME'):
                dest_filename = line[15:].strip()
            elif line.startswith('!REVISION'):
                revision = line[10:].strip()
            elif line.startswith('!MATCH_TYPE'):
                match_type = line[12:].strip()
            elif line.startswith('!MATCH_NAME'):
                match_name = line[12:].strip()
            elif line.startswith('!MATCH_UID'):
                match_uid = int(line[11:].strip(), 16)
            elif line.startswith('!WRITE_NAME'):
                write_name = line[12:].strip()
            elif line.startswith('!WRITE_ID'):
                write_id = int(line[10:].strip(), 0)
            elif line.startswith('!WRITE_CRC'):
                program_crc = int(line[11:].strip(), 16)

            elif line.startswith('!BEGIN_CONFIG'):
                is_reading_config = True
            elif line.startswith('!END_CONFIG'):
                is_reading_config = False
            elif line.startswith('!BEGIN_PROGRAM'):
                is_reading_program = True
            elif line.startswith('!END_PROGRAM'):
                is_reading_program = False

    return FWU(crc, dest_filename, revision, match_type, match_name, match_uid, write_name, write_id, config, program.splitlines(), program_crc)

# Main entrypoint
if __name__ == '__main__':
    fwu = fwu_parse(sys.argv[1])
    print(fwu)
import sys

# Adaptation from C equivalent

def stm32_crc32_fast(crc, word):
    NIBBLE_LU_TABLE = [0x00000000,0x04C11DB7,0x09823B6E,0x0D4326D9,0x130476DC,0x17C56B6B,0x1A864DB2,0x1E475005,0x2608EDB8,0x22C9F00F,0x2F8AD6D6,0x2B4BCB61,0x350C9B64,0x31CD86D3,0x3C8EA00A,0x384FBDBD]

    crc = crc ^ word
    
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]
    crc = ((crc << 4) & 0xFFFFFFFF) ^ NIBBLE_LU_TABLE[crc >> 28]

    return crc

def stm32_crc32_block(crc, buffer):
    for i in range(0, len(buffer), 4):
        crc = stm32_crc32_fast(crc, ord(bytes[i+3]) << 24 | ord(bytes[i+2]) << 16 | ord(bytes[i+1]) << 8 | ord(bytes[i+0]))

    return crc

def stm32_crc32_bytes(crc, buffer):
    for i in range(0, len(buffer), 4):
        crc = stm32_crc32_fast(crc, buffer[i+3] << 24 | buffer[i+2] << 16 | buffer[i+1] << 8 | buffer[i+0])

    return crc
#-----------------------------------------------------------------------------#
def test():
    try:
        in_file = open('tmp.gz', 'rb')
    except IOError:
        sys.stderr.write("error: can't open file.\n")
        sys.exit(1)

    bytes = in_file.read(1024)

    crc = stm32_crc32_block(0xffffffff, bytes)

    print(hex(crc))

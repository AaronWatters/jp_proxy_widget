
"""
Helpers for sending/receiving binary data as unicode
"""

import codecs

CODEC = 'hex_codec'

def hex_to_bytearray(hex):
    "decode a hex string to a binary bytearray."
    binary = codecs.decode(hex, CODEC)
    return bytearray(binary)

def bytearray_to_hex(binary):
    hexbytes = codecs.encode(binary, CODEC)
    return codecs.decode(hexbytes, "utf8")


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

if __name__=="__main__":
    bytestr = b"\x12\xff"
    array = bytearray(bytestr)
    hexstr = u"12ff"
    encoded = bytearray_to_hex(array)
    assert encoded == hexstr, "not same " + repr((encoded, hexstr))
    decoded = hex_to_bytearray(hexstr)
    assert type(decoded) is bytearray
    assert bytes(decoded) == bytestr
    # smoke test a json round trip...
    import json
    dumped = json.dumps([encoded])
    undumped = json.loads(dumped)
    assert undumped[0] == encoded
    print("ok " + repr((encoded, decoded)))

import unittest
from jp_proxy_widget import hex_codec

hexstr = u"12ff"
bytestr = b"\x12\xff"

class TestHexCodec(unittest.TestCase):

    def test_to_bytes(self):
        b = hex_codec.hex_to_bytearray(hexstr)
        self.assertEqual(b, bytestr)

    def test_to_unicode(self):
        s = hex_codec.bytearray_to_hex(bytestr)
        self.assertEqual(s, hexstr)

    def test_json_roundtrip(self):
        encoded = hexstr
        import json
        dumped = json.dumps([encoded])
        undumped = json.loads(dumped)
        assert undumped[0] == encoded

"""
Download files from Python values to client computer
using jp_proxy and FileSaver.js
"""

import jp_proxy_widget
from IPython.display import display
from traitlets import Unicode, HasTraits
import time

js_file = "js/Filesaver.js"

js_helper = """
// function(element) {
    // debugger;
    element.download = function(file_name, value, type) {
        // value can be string or Uint8Array
        var blob = new Blob([value], {type: type});
        element.saveAs(blob, file_name);
    };
//}
"""

def load_file_saver(to_proxy_widget, sleep=0.1):
    w = to_proxy_widget
    if not hasattr(to_proxy_widget, "saveAs_loaded"):
        w.require_js("saveAs", js_file)
        w.js_init(js_helper)
        w.flush()
        # sleep a little bit to allow javascript interpreter to sync
        time.sleep(sleep)
    w.saveAs_loaded = True

def saveAsUnicode(to_widget, file_name, unicode_string, type="text/plain;charset=utf-8"):
    w = to_widget
    load_file_saver(w)
    #element = w.element()
    #w(element.download(file_name, unicode_string, type))
    w.element.download(file_name, unicode_string, type)
    w.seg_flush()

def saveAsBinary(to_widget, file_name, byte_sequence, type="octet/stream"):
    # send the data as binary bytearray.
    data = bytearray(byte_sequence)
    w = to_widget
    load_file_saver(w)
    #element = w.element()
    #w(element.download(file_name, data, type))
    w.element.download(file_name, data, type)
    w.seg_flush()

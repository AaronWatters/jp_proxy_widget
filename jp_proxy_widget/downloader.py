"""
Download files from Python values to client computer
using jp_proxy and FileSaver.js
"""

import jp_proxy_widget
from IPython.display import display
from traitlets import Unicode, HasTraits
import time

js_file = "js/FileSaver.js"

def load_file_saver(to_proxy_widget, when_ready):
    if hasattr(to_proxy_widget, "saveAs_loaded"):
        return when_ready()
    to_proxy_widget.require_js("saveAs", js_file)
    to_proxy_widget.js_init("""
    debugger;
    element.download = function(name, content, type) {
        element.requirejs(["saveAs"], function(saveAs) {
            var the_blob = new Blob([content], {type: type});
            saveAs(the_blob, name);
        });
    };
    when_ready();
    """, when_ready=when_ready)
    to_proxy_widget.seg_flush()
    to_proxy_widget.saveAs_loaded = True

def saveAsUnicode(to_widget, file_name, unicode_string, type="text/plain;charset=utf-8"):
    w = to_widget
    def when_ready():
        w.element.download(file_name, unicode_string, type)
        # Use a segmented flush for large data if autoflush is disabled
        w.seg_flush()
    load_file_saver(w, when_ready)

def saveAsBinary(to_widget, file_name, byte_sequence, type="octet/stream"):
    # send the data as binary bytearray.
    data = bytearray(byte_sequence)
    w = to_widget
    def when_ready():
        w.element.download(file_name, data, type)
        # Use a segmented flush for large data if autoflush is disabled
        w.seg_flush()
    load_file_saver(w, when_ready)

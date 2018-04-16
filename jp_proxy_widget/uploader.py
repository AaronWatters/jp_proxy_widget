"""
Upload files to jupyter server location using jp_proxy.
"""

import jp_proxy_widget
from IPython.display import display

js_files = ["js/simple_upload_button.js"]

def _load_required_js(widget):
    widget.load_js_files(filenames=js_files)

def from_hex_iterator(hexcontent):
    for i in range(0, len(hexcontent), 2):
        hexcode = hexcontent[i: i+2]
        char = bytes([(int(hexcode, 16))])
        yield char

class UnicodeUploader:

    status = None
    uploaded_filename = None

    def __init__(self, html_title=None, content_callback=None, to_filename=None, size_limit=None):
        assert content_callback is None or to_filename is None, (
            "content_callback and to_filename are mutually exclusive, please do not provide both. "
            + repr((content_callback, to_filename))
        )
        assert content_callback is not None or to_filename is not None, (
            "content_callback or to_filename must be specified."
        )
        self.size_limit = size_limit
        self.to_filename = to_filename
        self.content_callback = content_callback
        w = self.widget = jp_proxy_widget.JSProxyWidget()
        _load_required_js(w)
        element = w.element()
        if html_title is not None:
            w(element.html(html_title)._null())
        level = 2
        options = self.upload_options()
        options["size_limit"] = size_limit
        proxy_callback = w.callback(self.widget_callback_handler, data="upload click", level=level)
        element = w.element()
        upload_button = element.simple_upload_button(proxy_callback, options)
        w(element.append(upload_button))
        w.flush()

    def show(self):
        display(self.widget)

    def default_content_callback(self, widget, name, content):
        to_filename = self.to_filename
        if to_filename == True:
            # use the name sent as the filename
            to_filename = name
        self.status = "writing " + repr(len(content)) + " to " + repr(to_filename)
        f = self.open_for_write(to_filename)
        f.write(content)
        f.close()
        self.status = "wrote " + repr(len(content)) + " to " + repr(to_filename)
        self.uploaded_filename = to_filename

    def widget_callback_handler(self, data, results):
        self.status = "upload callback called."
        file_info = results["0"]
        name = file_info["name"]
        content = self.get_content(file_info)
        content_callback = self.content_callback
        if content_callback is None:
            content_callback = self.default_content_callback
        self.status = "calling " + repr(content_callback)
        try:
            content_callback(self.widget, name, content)
        except Exception as e:
            self.status += "\n" + repr(content_callback) + " raised " + repr(e)
            raise

    def upload_options(self):
        "options for jquery upload plugin -- unicode, not hex"
        return {"hexidecimal": False}

    def open_for_write(self, filename):
        "open unicode file for write"
        return open(filename, "w")

    def get_content(self, file_info):
        "get unicode content from file_info"
        content = file_info["content"]
        return content

class BinaryUploader(UnicodeUploader):

    def upload_options(self):
        return {"hexidecimal": True}

    def open_for_write(self, filename):
        return open(filename, "wb")

    def get_content(self, file_info):
        hexcontent = file_info["hexcontent"]
        content = b"".join(from_hex_iterator(hexcontent))
        return content

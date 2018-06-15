"""
Upload files to jupyter server location or to Python callback using jp_proxy.
"""

import jp_proxy_widget
from jp_proxy_widget import hex_codec
from IPython.display import display
from traitlets import Unicode, HasTraits

js_files = ["js/simple_upload_button.js"]

def _load_required_js(widget):
    widget.load_js_files(filenames=js_files)

def from_hex_iterator(hexcontent):
    # xxxx try to optimize...
    for i in range(0, len(hexcontent), 2):
        hexcode = hexcontent[i: i+2]
        char = bytes(((int(hexcode, 16)),))
        yield char

class JavaScriptError(Exception):
    "Exception sent from javascript."

class UnicodeUploader(HasTraits):

    status = Unicode("")
    uploaded_filename = None
    segmented = None   # no segmentation -- use chunk size instead

    def __init__(self, html_title=None, content_callback=None, to_filename=None, size_limit=None,
        chunk_size=1000000):
        # by default segment files into chunks to avoid message size limits
        self.chunk_size = chunk_size
        assert content_callback is None or to_filename is None, (
            "content_callback and to_filename are mutually exclusive, please do not provide both. "
            + repr((content_callback, to_filename))
        )
        assert content_callback is not None or to_filename is not None, (
            "one of content_callback or to_filename must be specified."
        )
        self.size_limit = size_limit
        self.to_filename = to_filename
        self.content_callback = content_callback
        w = self.widget = jp_proxy_widget.JSProxyWidget()
        _load_required_js(w)
        element = w.element
        if html_title is not None:
            element.html(html_title)
        level = 2
        options = self.upload_options()
        options["size_limit"] = size_limit
        options["chunk_size"] = chunk_size
        #proxy_callback = w.callback(self.widget_callback_handler, data="upload click", level=level,
        #    segmented=self.segmented)
        #element = w.element()
        #upload_button = element.simple_upload_button(proxy_callback, options)
        w.js_init("""
            var upload_callback = function(data) {
                var content = data.content;
                if (!($.type(content) === "string")) {
                    content = data.hexcontent;
                }
                handle_chunk(data.status, data.name, content, data);
            }
            var upload_button = element.simple_upload_button(upload_callback, options);
            element.append(upload_button);
        """, handle_chunk=self.handle_chunk_wrapper, options=options)
        #w(element.append(upload_button))
        #w.flush()
        self.chunk_collector = []
        self.status = "initialized"

    def show(self):
        self.status = "displayed"
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

    """
    def widget_callback_handler(self, data, results):
        self.status = "upload callback called."
        try:
            file_info = results["0"]
            name = file_info["name"]
            status = file_info["status"]
            content = self.get_content(file_info)
            content_callback = self.content_callback
            return self.handle_chunk(status, name, content, file_info)
        except Exception as e:
            self.status = "callback exception: " + repr(e)
            raise"""

    output = None

    def handle_chunk_wrapper(self, status, name, content, file_info):
        """wrapper to allow output redirects for handle_chunk."""
        out = self.output
        if out is not None:
            with out:
                print("handling chunk " + repr(type(content)))
                self.handle_chunk(status, name, content, file_info)
        else:
            self.handle_chunk(status, name, content, file_info)

    def handle_chunk(self, status, name, content, file_info):
        "Handle one chunk of the file.  Override this method for peicewise delivery or error handling."
        if status == "error":
            msg = repr(file_info.get("message"))
            exc = JavaScriptError(msg)
            exc.file_info = file_info
            self.status = "Javascript sent exception " + msg
            self.chunk_collector = []
            raise exc
        if status == "more":
            self.chunk_collector.append(content)
            self.progress_callback(self.chunk_collector, file_info)
        else:
            assert status == "done", "Unknown status " + repr(status)
            self.save_chunks = self.chunk_collector
            self.chunk_collector.append(content)
            all_content = self.combine_chunks(self.chunk_collector)
            self.chunk_collector = []
            content_callback = self.content_callback
            if content_callback is None:
                content_callback = self.default_content_callback
            self.status = "calling " + repr(content_callback)
            try:
                content_callback(self.widget, name, all_content)
            except Exception as e:
                self.status += "\n" + repr(content_callback) + " raised " + repr(e)
                raise

    encoding_factor = 1

    def progress_callback(self, chunks, file_info):
        size = file_info["size"] * self.encoding_factor
        got = 0
        for c in chunks:
            got += len(c)
        pct = int((got * 100)/size)
        self.status = "received %s of %s (%s%%)" % (got, size, pct)

    def combine_chunks(self, chunk_list):
        return u"".join(chunk_list)

    def upload_options(self):
        "options for jquery upload plugin -- unicode, not hex"
        return {"hexidecimal": False}

    def open_for_write(self, filename):
        "open unicode file for write"
        return open(filename, "w")

    def get_content(self, file_info):
        "get unicode content from file_info"
        content = file_info.get("content")
        return content

class BinaryUploader(UnicodeUploader):

    encoding_factor = 2

    def upload_options(self):
        return {"hexidecimal": True}

    def open_for_write(self, filename):
        return open(filename, "wb")

    def get_content(self, file_info):
        return file_info.get("hexcontent")

    def combine_chunks(self, chunk_list):
        all_hex_content = "".join(chunk_list)
        #return b"".join(from_hex_iterator(all_hex_content))
        ba = hex_codec.hex_to_bytearray(all_hex_content)
        return bytes(ba)


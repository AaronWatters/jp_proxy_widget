import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from jp_proxy_widget import js_context
import tempfile
import os

class TestJsContext(unittest.TestCase):

    def test_local_path(self):
        f = tempfile.NamedTemporaryFile()
        name = f.name
        path = js_context.get_file_path(name)
        abspath = os.path.abspath(name)
        self.assertEqual(path, abspath)

    def test_local_path_relative_to_module(self):
        f = tempfile.NamedTemporaryFile()
        name = f.name
        path = js_context.get_file_path(name, relative_to_module=tempfile)
        abspath = os.path.abspath(name)
        self.assertEqual(path, abspath)

    def test_module_path(self):
        name = "js/simple.js"
        path = js_context.get_file_path(name,)
        abspath = os.path.abspath(name)
        assert abspath.endswith("jp_proxy_widget/js/simple.js")

    #@patch("jp_proxy_widget.js_context.requests.get")  # dunno why I had to comment this...
    def test_remote_content(
        self, 
        path="https://raw.githubusercontent.com/AaronWatters/jp_proxy_widget/master/README.md"):
        class response:
            text = "talks about jp_doodle and other things"
        save = js_context.requests.get
        js_context.requests.get = MagicMock(return_value=response)
        content = js_context.get_text_from_file_name(path)
        js_context.requests.get = save
        assert "jp_doodle" in content

    def test_local_content(self, path="js/simple.js"):
        content = js_context.get_text_from_file_name(path)
        assert "simple javascript" in content

    def test_byte_content(self, path="js/simple.js"):
        from unittest.mock import patch, mock_open
        byte_content = b"byte content"
        unicode_content = u"byte content"
        m = mock_open(read_data=byte_content)
        open_name = '%s.open' % js_context.__name__
        path = "js/simple.js"
        with patch(open_name, m):
            content = js_context.get_text_from_file_name(path)
        self.assertEqual(content, unicode_content)

    @patch("jp_proxy_widget.js_context.display")
    @patch("jp_proxy_widget.js_context.Javascript")
    def test_display_javacript(self, mock1, mock2):
        js_text = "debugger"
        js_context.display_javascript(None, js_text)
        assert mock1.called
        assert mock2.called
        assert mock2.called_with(data=js_text)

    @patch("jp_proxy_widget.js_context.display")
    @patch("jp_proxy_widget.js_context.HTML")
    def test_display_css(self, mock1, mock2):
        js_text = "bogus"
        js_context.display_css(None, js_text)
        assert mock1.called
        assert mock2.called

    def test_eval_javascript(self):
        class dummyRecord:
            def __call__(self, *args):
                pass
        window = dummyRecord()
        window.eval = MagicMock()
        widget = dummyRecord()
        widget.window = MagicMock(return_value=window)
        #widget.__call__ = MagicMock()
        widget.flush = MagicMock()
        js_context.eval_javascript(widget, "debugger")
        assert window.eval.called
        assert widget.flush.called


    @patch("jp_proxy_widget.js_context.print")
    @patch("jp_proxy_widget.js_context.time.sleep")
    @patch("jp_proxy_widget.js_context.EVALUATOR")
    def test_load_filenames(self, mock1, mock2, mock3):
        # call twice to exercise "no reload"
        widget = None
        filename = "js/simple.js"
        #filepath = js_context.get_file_path(filename)
        filenames = [filename]
        verbose = True
        evaluator = MagicMock()
        js_context.load_if_not_loaded(widget, filenames, verbose, evaluator=evaluator)
        loaded = set(js_context.LOADED_JAVASCRIPT)
        js_context.load_if_not_loaded(widget, filenames, verbose)
        reloaded = set(js_context.LOADED_JAVASCRIPT)
        self.assertEqual(loaded, reloaded)
        self.assertIn(filename, loaded)
        #assert mock1.called
        assert mock2.called
        assert mock3.called


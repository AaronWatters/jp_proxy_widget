import unittest
from unittest.mock import patch
from unittest.mock import MagicMock
from jp_proxy_widget import proxy_widget
import jp_proxy_widget
import tempfile
import os

class TestProxyWidget(unittest.TestCase):

    def test_path(self):
        # smoke test
        L = jp_proxy_widget._jupyter_nbextension_paths()
        self.assertEqual(type(L[0]), dict)

    def test_create(self):
        widget = jp_proxy_widget.JSProxyWidget()
        self.assertEqual(type(widget), jp_proxy_widget.JSProxyWidget)

    def test_set_element(self):
        "is this method used?"
        name = "name"
        value = "value"
        widget = proxy_widget.JSProxyWidget()
        m = widget.js_init = MagicMock(return_value=3)
        widget.set_element(name, value)
        m.assert_called_with("element[slot_name] = value;", slot_name=name, value=value)

    def test_get_value_async_smoke_test(self):
        "real test is in end_to_end_testing"
        js = "1 + 1"
        widget = proxy_widget.JSProxyWidget()
        m = widget.js_init = MagicMock(return_value=3)
        callback = None  # never called in smoke test
        widget.get_value_async(callback, js, debug=True)
        assert m.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.__call__")
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.flush")
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.uses_require")
    def test_js_init_smoke_test(self, mock1, mock2, mock3):
        for r in (True, False):
            widget = proxy_widget.JSProxyWidget()
            widget._needs_requirejs = r
            def f_callable(x):
                return x + 3
            widget.js_init(
                "console.log('not really executed')",
                num=3.14,
                dicitonary=dict(hello="a greeting", oof="an interjection"),
                L=[2,3,5,7,11],
                f=f_callable
            )
        assert mock1.called
        assert mock2.called
        assert mock3.called

    @patch("jp_proxy_widget.proxy_widget.print")
    def test_handle_error_msg(self, m):
        widget = proxy_widget.JSProxyWidget()
        widget.handle_error_msg("att", "old", "new")
        assert m.called

    #@patch("proxy_widget.JSProxyWidget.send_commands")
    def test_handle_rendered(self):
        widget = proxy_widget.JSProxyWidget()
        #widget.commands_awaiting_render = ["bogus"]
        widget.buffered_commands = ["bogus"]
        m = widget.send_commands = MagicMock()
        #widget.handle_rendered("att", "old", "new")
        widget.rendered = True
        assert m.called
        self.assertEqual(widget.status, "Rendered.")
    
    #@patch("proxy_widget.JSProxyWidget.send_commands")
    def test_handle_rendered_error(self):
        widget = proxy_widget.JSProxyWidget()
        widget.buffered_commands = ["bogus"]
        m = widget.send_commands = MagicMock(side_effect=KeyError('foo'))
        with self.assertRaises(KeyError):
            #widget.handle_rendered("att", "old", "new")
            widget.rendered = True
        assert m.called
        #self.assertEqual(widget.status, "Rendered.")

    def test_send_custom_message(self):
        widget = proxy_widget.JSProxyWidget()
        m = widget.send = MagicMock()
        widget.send_custom_message("indicator", "payload")
        assert m.called

    def test_handle_custom_message_wrapper(self):
        widget = proxy_widget.JSProxyWidget()
        widget.output = None
        m = widget.handle_custom_message = MagicMock()
        widget.handle_custom_message_wrapper(None, None, None)
        assert m.called

    def test_handle_custom_message_redir(self):
        widget = proxy_widget.JSProxyWidget()
        class mgr:
            def __init__(self):
                self.entered = self.exitted = False
            def __enter__(self):
                self.entered = True
            def __exit__(self, *args):
                self.exitted = True
        c = widget.output = mgr()
        m = widget.handle_custom_message = MagicMock()
        widget.handle_custom_message_wrapper(None, None, None)
        assert m.called
        assert c.entered
        assert c.exitted

    @patch("jp_proxy_widget.proxy_widget.widgets.Output")
    @patch("jp_proxy_widget.proxy_widget.widgets.Text")
    @patch("jp_proxy_widget.proxy_widget.widgets.VBox")
    @patch("jp_proxy_widget.traitlets.directional_link")
    @patch("jp_proxy_widget.print")
    def test_debugging_display(self, *mocks):
        for tagline in ("", "hello"):
            for border in ("", "1px"):
                widget = proxy_widget.JSProxyWidget()
                widget.debugging_display(tagline, border)
        #for (i, mock) in enumerate(mocks):
        #    assert mock.called, "not called: " + repr(i)
    
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.handle_results")
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.handle_callback_results")
    def test_handle_custom_message(self, *mocks):
        i = proxy_widget.INDICATOR
        p = proxy_widget.PAYLOAD
        data_list = [
            {i: proxy_widget.RESULTS, p: "bogus payload"},
            {i: proxy_widget.CALLBACK_RESULTS, p: "bogus payload"},
            {i: proxy_widget.JSON_CB_FINAL, p: "[1,2,3]"},
            {i: proxy_widget.JSON_CB_FRAGMENT, p: "bogus payload"},
            {i: "unknown indicator", p: "bogus payload"},
        ]
        for data in data_list:
            widget = proxy_widget.JSProxyWidget()
            widget.handle_custom_message(None, data)

    def test_handle_custom_message_error(self, *mocks):
        i = proxy_widget.INDICATOR
        p = proxy_widget.PAYLOAD
        data = {i: proxy_widget.RESULTS, p: "bogus payload"}
        widget = proxy_widget.JSProxyWidget()
        m = widget.handle_results = MagicMock(side_effect=KeyError('foo'))
        with self.assertRaises(KeyError):
            widget.handle_custom_message(None, data)

    def test_uid(self):
        widget = proxy_widget.JSProxyWidget()
        u1 = widget.unique_id()
        u2 = widget.unique_id()
        assert u1 != u2

    def test_widget_call(self):
        widget = proxy_widget.JSProxyWidget()
        m = widget.flush = MagicMock()
        widget.send_commands = MagicMock()
        widget.auto_flush = True
        widget("console.log('not executed')")
        assert m.called

    def test_seg_flush(self):
        widget = proxy_widget.JSProxyWidget()
        m = widget.flush = MagicMock()
        widget.seg_flush(None, None, None)
        assert m.called

    def test_flush(self):
        widget = proxy_widget.JSProxyWidget()
        m = widget.send_commands = MagicMock()
        widget.flush()
        assert not m.called
        widget.rendered = True
        widget.flush()
        assert m.called
        widget.error_on_flush = True
        with self.assertRaises(ValueError):
            widget.flush()

    def test_delay_flush(self):
        widget = proxy_widget.JSProxyWidget()
        m = widget.send_commands = MagicMock()
        widget.rendered = True
        widget.flush()
        assert m.called
        m = widget.send_commands = MagicMock()
        with widget.delay_flush():
            widget.element.do_something_in_javascript()
            assert not m.called
            assert len(widget.buffered_commands) > 0
        assert m.called
        assert len(widget.buffered_commands) == 0
        
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.__call__")
    def test_save(self, mc):
        class dummy_elt:
            def _set(self, name, ref):
                setattr(self, name, ref)
        widget = proxy_widget.JSProxyWidget()
        widget.send_commands = MagicMock()
        e = dummy_elt()
        m = widget.get_element = MagicMock(return_value=e)
        v = "the value"
        k = "apples"
        x = widget.save(k, v)
        #self.assertEqual(e.apples, v)
        #self.assertEqual(e.apples, x)
        assert m.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_files")
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_css")
    def test_check_jquery(self, *mocks):
        on_success = MagicMock()
        widget = proxy_widget.JSProxyWidget()
        widget.check_jquery(on_success, force=True)
        assert on_success.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_files")
    def test_require_already_loaded(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        e = widget.element = RequireMockElement()
        e.require_is_loaded = True
        proxy_widget.JSProxyWidget._require_checked = True
        action = MagicMock()
        widget.uses_require(action)
        assert action.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_files")
    def test_require_wont_load(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        e = widget.element = RequireMockElement()
        e.require_is_loaded = False
        proxy_widget.JSProxyWidget._require_checked = True
        action = MagicMock()
        with self.assertRaises(ImportError):
            widget.uses_require(action)
        assert not action.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_files")
    def test_require_loads(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        e = widget.element = RequireMockElement()
        e.require_is_loaded = False
        proxy_widget.JSProxyWidget._require_checked = False
        action = MagicMock()
        widget.uses_require(action)
        assert action.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_files")
    def test_require_loads_action_fails(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        e = widget.element = RequireMockElement()
        e.require_is_loaded = False
        proxy_widget.JSProxyWidget._require_checked = False
        action = MagicMock(side_effect=KeyError('foo'))
        #with self.assertRaises(KeyError):
        widget.error_msg = ""
        widget.uses_require(action)
        assert action.called
        assert widget.error_msg.startswith("require.js delayed action exception")

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_files")
    def test_require_loads_delayed(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        e = widget.element = RequireMockElement()
        e.require_is_loaded = False
        e.when_loaded_delayed = True
        proxy_widget.JSProxyWidget._require_checked = False
        action1 = MagicMock()
        action2 = MagicMock()
        widget.uses_require(action1)
        widget.uses_require(action2)
        assert not action1.called
        assert not action2.called
        e.load_completed()
        assert action1.called
        assert action2.called

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_css_text")
    def test_load_css(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        widget.load_css("js/simple.css")

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.__call__")
    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_css_command")
    def test_load_css_text(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        widget.load_css_text("js/simple.css", "fake content")

    @patch("jp_proxy_widget.proxy_widget.JSProxyWidget.load_js_module_text")
    def test_require_js(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        def uses_require(action):
            action()
        widget.uses_require = uses_require
        widget.require_js("js/simple.css", "js/simple.css")

    def test_load_js_module_text(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        m = widget.element._load_js_module = MagicMock()
        widget.load_js_module_text("name", "text")
        assert m.called

    def test_save_new(self, *mocks):
        widget = proxy_widget.JSProxyWidget()
        #m = widget.element.New = MagicMock()
        m2 = widget.save = MagicMock()
        widget.save_new("name", "constructor", [1,2,3])
        #assert m.called
        assert m2.called

    def test_save_function(self):
        widget = proxy_widget.JSProxyWidget()
        m = widget.save_new = MagicMock()
        class fakeWindow:
            Function = None
        m2 = widget.window = MagicMock(return_value=fakeWindow)
        widget.save_function("name", ("a", "b"), "return a+b")
        assert m.called
        assert m2.called

    @patch("jp_proxy_widget.proxy_widget.print")
    def test_handle_results(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.verbose = True
        idnt = 1
        cb = MagicMock()
        i2c = widget.identifier_to_callback = {idnt: cb}
        v = "the value"
        new_results = [idnt, v]
        widget.handle_results(new_results)
        assert cb.called
        assert len(i2c) == 0

    @patch("jp_proxy_widget.proxy_widget.print")
    def test_handle_results_error(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.verbose = True
        idnt = 1
        cb = MagicMock(side_effect=KeyError('foo'))
        i2c = widget.identifier_to_callback = {idnt: cb}
        v = "the value"
        new_results = [idnt, v]
        with self.assertRaises(KeyError):
            widget.handle_results(new_results)
        assert cb.called
        assert len(i2c) == 0

    @patch("jp_proxy_widget.proxy_widget.print")
    def test_callback_results(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.verbose = True
        new_results = [1,2,[3],4]
        [identifier, json_value, arguments, counter] = new_results
        cb = MagicMock()
        i2c = widget.identifier_to_callback = {identifier: cb}
        widget.handle_callback_results(new_results)
        assert cb.called
        assert len(i2c) == 1

    @patch("jp_proxy_widget.proxy_widget.print")
    def test_callback_results_error(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.verbose = True
        new_results = [1,2,[3],4]
        [identifier, json_value, arguments, counter] = new_results
        cb = MagicMock(side_effect=KeyError('foo'))
        i2c = widget.identifier_to_callback = {identifier: cb}
        with self.assertRaises(KeyError):
            widget.handle_callback_results(new_results)
        assert cb.called
        assert len(i2c) == 1
        assert widget.error_msg.startswith("Handle callback results")

    def test_send_command_before_render(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.rendered = False
        command = [1,2,3]
        cb = MagicMock()
        before = len(widget.buffered_commands)
        widget.send_command(command, cb)
        assert not cb.called
        assert len(widget.buffered_commands) == before + 1
        return widget

    def test_send_command_after_rendered(self, *args):
        widget = self.test_send_command_before_render()
        widget.rendered = True
        command = [2,3,4]
        cb = MagicMock()
        s = widget.send_custom_message = MagicMock()
        widget.send_command(command, cb)
        assert not widget.buffered_commands
        assert not cb.called
        assert s.called

    def test_send_command_segmented(self, *args):
        widget = self.test_send_command_before_render()
        widget.rendered = True
        command = [2,3,4]
        cb = MagicMock()
        s = widget.send_segmented_message = MagicMock()
        widget.send_commands([command], cb, segmented=1000)
        assert not widget.buffered_commands
        assert not cb.called
        assert s.called

    def test_send_segmented_message(self, *args):
        payload = list(range(1000))
        widget = proxy_widget.JSProxyWidget()
        s = widget.send_custom_message = MagicMock()
        widget.send_segmented_message("frag", "final", payload, 100)
        assert s.called


    """
    def test_evaluate(self, *args):
        payload = list(range(1000))
        widget = proxy_widget.JSProxyWidget()
        e = widget.evaluate_commands = MagicMock(return_value=[123])
        x = widget.evaluate(payload)
        assert e.called
        assert x == 123

    @patch("jp_proxy_widget.proxy_widget.ip")
    def test_evaluate_commands(self, *args):
        commands = list(range(100))
        results_in = [33]
        widget = proxy_widget.JSProxyWidget()
        #s = widget.send_commands = MagicMock()
        callback = [None]
        test = MagicMock()
        def send_commands(iter, cb, lvl):
            callback[0] = cb
        widget.send_commands = send_commands
        def do_one_iteration():
            callback[0](results_in)
            test()
        proxy_widget.ip = MagicMock()
        proxy_widget.ip.kernel = MagicMock()
        proxy_widget.ip.kernel.do_one_iteration = do_one_iteration
        values = widget.evaluate_commands(commands)
        assert test.called
        self.assertEqual(results_in, values)"""

    #@patch("jp_proxy_widget.proxy_widget.ip")
    def test_evaluate_commands_timeout(self, *args):
        commands = list(range(100))
        results_in = [33]
        widget = proxy_widget.JSProxyWidget()
        #s = widget.send_commands = MagicMock()
        callback = [None]
        test = MagicMock()
        def send_commands(iter, cb, lvl):
            callback[0] = cb
        widget.send_commands = send_commands
        def do_one_iteration():
            callback[0](results_in)
            test()
        #proxy_widget.ip = MagicMock()
        #proxy_widget.ip.kernel = MagicMock()
        #proxy_widget.ip.kernel.do_one_iteration = do_one_iteration
        with self.assertRaises(Exception):
            values = widget.evaluate_commands(commands, timeout=-1)

    def test_seg_callback(self, *args):
        widget = proxy_widget.JSProxyWidget()
        def f(*args):
            return args
        data = (1,2,3)
        widget.seg_callback(f, data)

    def test_callable(self, *args):
        widget = proxy_widget.JSProxyWidget()
        def f(*args):
            #print("got args: " + repr(args))
            return args
        c = widget.callable(f)
        c2 = widget.callable(c)
        assert c is c2
        assert type(c) is jp_proxy_widget.CallMaker
        # call the callback
        identifier = c.args[0]
        callback = widget.identifier_to_callback[identifier]
        callback("dummy", {"0": "the first argument"})
        #self.assertEqual(c.args[1], 1)
        #(count, data, level, segmented) = c.args

    def test_forget_callable(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.identifier_to_callback = {1: list, 2: dict}
        widget.forget_callback(list)
        self.assertEqual(list(widget.identifier_to_callback.keys()), [2])

    def test_js_debug(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.get_element = MagicMock()
        widget.send_command = MagicMock()
        widget.js_debug()

    @patch("jp_proxy_widget.proxy_widget.print")
    def test_print_status(self, p):
        widget = proxy_widget.JSProxyWidget()
        widget.print_status()
        assert p.called

    def test_load_js_files(self, *args):
        widget = proxy_widget.JSProxyWidget()
        def mock_callable(c):
            return c
        widget.callable = mock_callable
        def mock_test_js_loaded(paths, dummy, callback):
            callback()
        widget.element.test_js_loaded = mock_test_js_loaded
        widget.send_command = MagicMock()
        widget.load_js_files(["js/simple.js"], force=False)
        widget.load_js_files(["js/simple.js"], force=True)

    def test_load_css_command(self, *args):
        widget = proxy_widget.JSProxyWidget()
        widget.load_css_command("dummy.css", "this is not really css text content")

    def test_validate_commands(self, *args):
        call_args = [
            ["element"],
            ["window"],
        ]
        [numerical_identifier, untranslated_data, level, segmented] = [123, "whatever", 2, 10000]
        commands = call_args + [
            ["method", ["element"], "method_name"] + call_args,
            ["function", ["element"]] + call_args,
            ["id", "untranslated"],
            ["bytes", u"12ff"],
            ["list"] + call_args,
            ["dict", {"key": ["element"]}],
            ["callback", numerical_identifier, untranslated_data, level, segmented],
            ["get", ["element"], "whatever"],
            ["set", ["element"], "whatever", ["window"]],
            ["null", ["element"]],
            dict,
        ]
        widget = proxy_widget.JSProxyWidget()
        widget.validate_commands(commands)
        with self.assertRaises(ValueError):
            widget.validate_commands([["BAD_INDICATOR", "OTHER", "STUFF"]])
        with self.assertRaises(ValueError):
            widget.validate_command("TOP LEVEL COMMAND MUST BE A LIST", top=True)

    def test_indent(self, *args):
        indented = proxy_widget.indent_string("a\nx", level=3, indent=" ")
        self.assertEquals("a\n   x", indented)

    def test_to_javascript(self, *args):
        thing = [
            {"a": proxy_widget.CommandMaker("window")},
            "a string",
            ["a string in a list"],
            bytearray(b"a byte array"),
        ]
        js = proxy_widget.to_javascript(thing)

    def test_element_wrapper(self, *args):
        widget = proxy_widget.JSProxyWidget()
        element = MagicMock()
        widget.get_element = MagicMock(returns=element)
        element._set = MagicMock()
        wrapper = proxy_widget.ElementWrapper(widget)
        get_attribute = wrapper.some_attribute
        set_attribute = wrapper._set("some_attribute", "some value")
        assert widget.get_element.called

    def test_command_maker(self, *args):
        m = proxy_widget.CommandMaker("window")
        exercised_methods = [
            repr(m),
            m.javascript(),
            m._cmd(),
            m.some_attribute,
            m._set("an_attribute", "some_value"),
            m._null(),
        ]
        self.assertEquals(len(exercised_methods), 6)
        with self.assertRaises(ValueError):
            m("Cannot call a top level command maker")

    def test_call_maker(self, *args):
        for kind in ["function", "method", "unknown"]:
            c = proxy_widget.CallMaker(kind, proxy_widget.CommandMaker("window"), "arg2")
            exercised = [
                c.javascript(),
                c("call returned value"),
                c._cmd()
            ]
            self.assertEquals(len(exercised), 3)

    def test_method_maker(self, *args):
        c = proxy_widget.MethodMaker(proxy_widget.CommandMaker("window"), "method_name")
        exercised = [
            c.javascript(),
            c("call the method"),
            c._cmd()
        ]
        self.assertEquals(len(exercised), 3)

    def test_literal_maker(self, *args):
        for thing in (["a", "list"], {"a": "dictionary"}, bytearray(b"a bytearray")):
            c = proxy_widget.LiteralMaker(thing)
            exercised = [
                c.javascript(),
                c._cmd()
            ]
            self.assertEquals(len(exercised), 2)
        with self.assertRaises(ValueError):
            c = proxy_widget.LiteralMaker(proxy_widget) # can't translate a module
            c._cmd()

    def test_set_maker(self, *args):
        c = proxy_widget.SetMaker(proxy_widget.CommandMaker("window"), "some_attribute", "some_value")
        exercised = [
            c.javascript(),
            c._cmd()
        ]
        self.assertEquals(len(exercised), 2)

    def test_loader(self, *args):
        indicator = proxy_widget.LOAD_INDICATORS[0]
        c = proxy_widget.Loader(indicator, "bogus_name", "bogus content")
        exercised = [
            c._cmd()
        ]
        self.assertEquals(len(exercised), 1)
        with self.assertRaises(NotImplementedError):
            test = c.javascript()

    def test_debug_check_commands(self, *args):
        cmds = [
            None,
            123,
            123.4,
            "a string",
            ("a", "tuple"),
            {"a": "dict"},
            ["another", "list"],
            True,
            False,
        ]
        test = proxy_widget.debug_check_commands(cmds)
        with self.assertRaises(proxy_widget.InvalidCommand):
            proxy_widget.debug_check_commands([proxy_widget])

    def test_wrap_callables(self, *args):
        widget = proxy_widget.JSProxyWidget()
        binary = bytearray(b"\x12\xff binary bytes")
        string_value = "just a string"
        int_value = -123
        float_value = 45.6
        json_dictionary = {"keys": None, "must": 321, "be": [6, 12], "strings": "values", "can": ["be", "any json"]}
        list_value = [9, string_value, json_dictionary]
        all = [binary, string_value, int_value, float_value, json_dictionary, list_value]
        for unwrapped in all + [all]:
            wrapped = widget.wrap_callables(unwrapped)
            self.assertEqual(wrapped, unwrapped)

    def test_cmd_str(self, *args):
        s = "a string"
        L = proxy_widget.LiteralMaker(s)
        self.assertEqual(L._cmd(), s)

    def test_lazy_get(self, *args):
        widget = proxy_widget.JSProxyWidget()
        get = widget.element["AnyAttribute"]
        method_call = get("called")
        self.assertIsInstance(method_call, proxy_widget.LazyMethodCall)
        call_attribute = method_call["someOtherAttribute"]
        self.assertIsInstance(call_attribute, proxy_widget.LazyGet)
        self.assertIsInstance(repr(call_attribute), str)  # exercise the repr method

    def test_clean_dict(self, *args):
        import numpy as np
        A = np.array([1.1, 2.2], dtype=np.float32)
        a1 = A[1]
        assert type(a1) is not float
        D = proxy_widget.clean_dict(tuple=(1,2,3), array=A, np_float=a1, missing=None)
        self.assertEqual(D, dict(tuple=[1,2,3], array=A.tolist(), np_float=float(a1)))
        self.assertEqual(type(D["np_float"]), float)

    @patch("jp_proxy_widget.proxy_widget.run_ui_poll_loop")
    def test_evaluate_success(self, *args):
        widget = proxy_widget.JSProxyWidget()
        def fake_poll(*args):
            widget._synced_command_evaluated = True
            widget._synced_command_result = 42
        proxy_widget.run_ui_poll_loop = fake_poll
        get_value = widget.element["AnyAttribute"].sync_value(ms_delay=10)
        self.assertEqual(get_value, 42)

    @patch("jp_proxy_widget.proxy_widget.run_ui_poll_loop")
    def test_evaluate_exception(self, *args):
        widget = proxy_widget.JSProxyWidget()
        def fake_poll(*args):
            widget._synced_command_evaluated = True
            widget._synced_command_result = "SOMETHING WENT WRONG"
            widget.error_msg = "SOMETHING WENT WRONG"
        proxy_widget.run_ui_poll_loop = fake_poll
        with self.assertRaises(proxy_widget.JavascriptException):
            get_value = widget.element["AnyAttribute"].sync_value(ms_delay=10)

    def test_on_rendered(self, *args):
        widget = proxy_widget.JSProxyWidget()
        def fake_js_init(js, call_it):
            call_it()
        widget.js_init = fake_js_init
        m = MagicMock()
        widget.on_rendered(m, "some", "arguments")
        assert m.called

class RequireMockElement:
    "Used for mocking the element when testing loading requirejs"
    require_is_loaded = False
    when_loaded_succeeds = True
    when_loaded_delayed = False
    alias_called = False
    load_called = False

    def alias_require(self, require_ok, load_require):
        self.alias_called = True
        if self.require_is_loaded:
            return require_ok()
        else:
            return load_require()

    def when_loaded(self, paths, success, failure):
        self.load_called = True
        if self.when_loaded_succeeds:
            if self.when_loaded_delayed:
                self.delayed_success = success
            else:
                self.require_is_loaded = True
                success()
        else:
            failure()
    
    def load_completed(self):
        self.require_is_loaded = True
        self.delayed_success()



"""
This is an implementation of a generic "javascript proxy" Jupyter notebook widget.
The idea is that for many purposes this widget will make it easy to use javascript
components without having to implement the "javascript view" side of the widget.

This in-module documentation constitutes implementation/design notes
which does not explain how to use the module from a user perspective.
For end-user API documentation please see the example notebooks provided
in the source repository.

The strategy is to pass a sequence of encoded javascript "commands" as a JSON
object to the generic widget proxy and have the proxy execute javascript actions
in response to the commands.  The implementation uses Python and Javascript
introspection features to map Python expressions to similar Javascript expressions.
Commands can be chained using "chaining".

(object.method1(...).
    method2(...).
    method3(...)
    )

Results for the last command of the chain are passed back to the
Python widget controller object (to a restricted recursive depth)
except that non-JSON permitted values are mapped to None.

Here are notes on the encoding function E for the JSON commands and their interpretation
as javascript actions:

WIDGET INTERFACE: widget.get_element()
JSON ENCODING: ["element"]
JAVASCRIPT ACTION: get the this.$$el element for the widget.
JAVASCRIPT RESULT: this.$el
PASSED TO PYTHON: This should never be the end of the chain!

WIDGET INTERFACE: widget.window()
JSON ENCODING: ["window"]
JAVASCRIPT ACTION: get the global namespace (window object)
JAVASCRIPT RESULT: window object
PASSED TO PYTHON: This should never be the end of the chain!

WIDGET INTERFACE: <target>.method(<arg0>, <arg1>, ..., <argn>)
  or for non-python names <target>.__getattr___("$method")(<arg0>...)
JSON ENCODING: ["method", target, method_name, arg0, ..., argn]
JAVASCRIPT ACTION: E(target).method_name(E(arg0), E(arg1), ..., E(argn))
JAVASCRIPT RESULT: Result of method call.
PASSED TO PYTHON: Result of method call in JSON translation.

WIDGET INTERFACE: (this is not exposed to the widget directly)
JSON ENCODING: ["id", X]
JAVASCRIPT ACTION/RESULT: X -- untranslated JSON object.
PASSED TO PYTHON: X (but it should never be the last in the chain)

WIDGET INTERFACE: (not exposed)
JSON ENCODING: ["list", x0, x1, ..., xn]
JAVASCRIPT ACTION/RESULT: [E[x0], E[x1], ..., E[xn]]  -- recursively translated list.
PASSED TO PYTHON: should never be returned.

WIDGET INTERFACE: (not exposed)
JSON ENCODING: ["dict", {k0: v0, ..., kn: vn}]
JAVASCRIPT ACTION/RESULT: {k0: E(v0), ..., kn: E(vn)} -- recursively translated mapping.
PASSED TO PYTHON: should never be returned.

WIDGET INTERFACE: widget.callback(function, untranslated_data, depth=1)
JSON ENCODING: ["callback", numerical_identifier, untranslated_data]
JAVASCRIPT ACTION: create a javascript callback function which triggers 
   a python call to function(js_parameters, untranslated_data).
   The depth parameter controls the recursion level for translating the
   callback parameters to JSON when they are passed back to Python.
   The callback function should have the signature
       callback(untranslated_data, callback_arguments_json)
PASSED TO PYTHON: should never be returned.

WIDGET INTERFACE: target.attribute_name
   or for non-python names <target>.__getattr___("$attr")
JSON ENCODING: ["get", target, attribute_name]
JAVASCRIPT ACTION/RESULT: E(target).attribute_name
PASSED TO PYTHON: The value of the javascript property

WIDGET INTERFACE: <target>._set(attribute_name, <value>)
JSON ENCODING: ["set", target, attribute_name, value]
JAVASCRIPT ACTION: E(target).attribute_name = E(value)
JAVASCRIPT RESULT: E(target) for chaining.
PASSED TO PYTHON: E(target) translated to JSON (probably should never be last in chain)

WIDGET INTERFACE: not directly exposed.
JSON ENCODING: not_a_list
JAVASCRIPT ACTION: not_a_list -- other values are not translated
PASSED TO PYTHON: This should not be the end of the chain.

WIDGET INTERFACE: widget.new(<target>. <arg0>, ..., <argn>)
JSON ENCODING: ["new", target, arg0, ... argn]
JAVASCRIPT ACTION: thing = E(target); result = new E(arg0, ... argn)
PASSED TO PYTHON: This should not be the end of the chain.

WIDGET INTERFACE: <target>._null.
JSON ENCODING: ["null", target]
JAVASCRIPT ACTION: execute E(target) and discard the final value to prevent 
   large structures from propagating when not needed.  This is an 
   optimization to prevent unneeded communication.
PASSED TO PYTHON: None

"""

import ipywidgets as widgets
from traitlets import Unicode
import time
import IPython
from IPython.display import display, HTML
import traitlets
import json
#import threading
import types
import traceback
from . import js_context
from .hex_codec import hex_to_bytearray, bytearray_to_hex
from pprint import pprint
import numpy as np
from jupyter_ui_poll import run_ui_poll_loop

# In the IPython context get_ipython is a builtin.
# get a reference to the IPython notebook object.
#ip = IPython.get_ipython()   # not used

# For creating unique DOM identities
IDENTITY_COUNTER = [int(time.time() * 100) % 10000000]

# String constants for messaging
INDICATOR = "indicator"
PAYLOAD = "payload"
RESULTS = "results"
CALLBACK_RESULTS = "callback_results"
JSON_CB_FRAGMENT = "jcb_results"
JSON_CB_FINAL = "jcb_final"
COMMANDS = "commands"
COMMANDS_FRAGMENT = "cm_fragment"
COMMANDS_FINAL = "cm_final"
LOAD_CSS = "load_css"
LOAD_JS = "load_js"
LOAD_INDICATORS = [LOAD_CSS, LOAD_JS]

# This slot name is used to support D3-style chaining under some circumstances
FRAGILE_JS_REFERENCE = "_FRAGILE_JS_REFERENCE"

# Reference used for method resolution
FRAGILE_THIS = "_FRAGILE_THIS"

SEND_FRAGILE_JS_REFERENCE = "_SEND_FRAGILE_JS_REFERENCE"

# Message segmentation size default
BIG_SEGMENT = 1000000

class SyncTimeOutError(RuntimeError):
    "The sync operation between the kernel and Javascript timed out."

class JavascriptException(ValueError):
    "The sync operation caused an exception in the Javascript interpreter."


@widgets.register
class JSProxyWidget(widgets.DOMWidget):
    """Introspective javascript proxy widget.""" 
    _view_name = Unicode('JSProxyView').tag(sync=True)
    _model_name = Unicode('JSProxyModel').tag(sync=True)
    _view_module = Unicode('jp_proxy_widget').tag(sync=True)
    _model_module = Unicode('jp_proxy_widget').tag(sync=True)
    _view_module_version = Unicode('^1.0.9').tag(sync=True)
    _model_module_version = Unicode('^1.0.9').tag(sync=True)

    # traitlet port to use for sending commands to javascript
    #commands = traitlets.List([], sync=True)

    # Rendered flag sent by JS view after render is complete.
    rendered = traitlets.Bool(False, sync=True)

    status = traitlets.Unicode("Not initialized", sync=True)

    error_msg = traitlets.Unicode("No error", sync=True)

    # increment this after every flush to force a sync?
    _send_counter = traitlets.Integer(0, sync=True)

    verbose = False

    # Set to automatically flush messages to javascript side without buffering after render.
    auto_flush = True

    def __init__(self, *pargs, **kwargs):
        super(JSProxyWidget, self).__init__(*pargs, **kwargs)
        # top level access for element operations
        self.element = ElementWrapper(self)
        self.counter = 0
        self.count_to_results_callback = {}
        self.default_event_callback = None
        self.identifier_to_callback = {}
        self.callable_cache = {}
        #self.callback_to_identifier = {}
        #self.on_trait_change(self.handle_callback_results, "callback_results")
        #self.on_trait_change(self.handle_results, "results")
        self.on_trait_change(self.handle_rendered, "rendered")
        self.on_trait_change(self.handle_error_msg, "error_msg")
        ##pr "registered on_msg(handle_custom_message)"
        self.on_msg(self.handle_custom_message_wrapper)
        self.buffered_commands = []
        #self.commands_awaiting_render = []
        self.last_commands_sent = []
        self.last_callback_results = None
        self.results = []
        self.status = "Not yet rendered"
        self.last_attribute = None
        # Used for D3 style "chaining" -- reference to last object reference cached on JS side
        self.last_fragile_reference = None
        #self.executing_fragile = False
        # standard initialization in javascript
        self.js_init("""
            // make the window accessible through the element
            element.window = window;

            // Initialize caching slots.
            element._FRAGILE_THIS = null;
            element._FRAGILE_JS_REFERENCE = null;

            // The following is used for sending synchronous values.
            element._SEND_FRAGILE_JS_REFERENCE = function(ms_delay) {
                // xxxxx add a delay to allow the Python side to be ready for the response (???)
                ms_delay = ms_delay || 100;
                var ref = element._FRAGILE_JS_REFERENCE;
                var delayed = function () {
                    RECEIVE_FRAGILE_REFERENCE(ref);
                };
                setTimeout(delayed, ms_delay);
            };
        """, RECEIVE_FRAGILE_REFERENCE=self._RECEIVE_FRAGILE_REFERENCE, callable_level=5)

    def set_element(self, slot_name, value):
        """
        Map value to javascript and attach it as element[slot_name].
        """
        self.js_init("element[slot_name] = value;", slot_name=slot_name, value=value)

    def get_value_async(self, callback, javascript_expression, debug=False):
        """
        Evaluate the Javascript expression and send the result value to the callback as callback(value) asynchronously.
        """
        codeList = []
        codeList.append("// get_value_async")
        if debug:
            codeList.append("debugger;")
        codeList.append("callback(" + javascript_expression + ");")
        code = "\n".join(codeList)
        self.js_init(code, callback=callback)

    def js_init(self, js_function_body, callable_level=3, **other_arguments):
        """
        Run special purpose javascript initialization code.
        The function body is provided with the element as a free variable.
        """
        #pr ("js_init")
        #pr(js_function_body)
        other_argument_names = list(other_arguments.keys())
        #pr ("other names", other_argument_names)
        def listiffy(v):
            "convert tuples and elements of tuples to lists"
            type_v = type(v)
            if type_v in [tuple, list]:
                return list(listiffy(x) for x in v)
            elif type_v is dict:
                return dict((a, listiffy(b)) for (a,b) in v.items())
            else:
                return v
        def map_value(v):
            #if callable(v):
            #    return self.callable(v, level=callable_level)
            v = self.wrap_callables(v, callable_level=callable_level)
            return listiffy(v)
        other_argument_values = [map_value(other_arguments[name]) for name in other_argument_names]
        #pr( "other_values", other_argument_values)
        #other_argument_values = [other_arguments[name] for name in other_argument_names]
        #other_argument_values = self.wrap_callables(other_argument_values)
        argument_names = list(["element"] + other_argument_names)
        argument_values = list([self.get_element()] + other_argument_values)
        function = self.function(argument_names, js_function_body)
        function_call = function(*argument_values)
        # execute the function call on the javascript side.
        def action():
            self(function_call)
            self.flush()
        if self._needs_requirejs:
            # defer action until require is defined
            self.uses_require(action)
        else:
            # just execute it
            action()

    def wrap_callables(self, x, callable_level=3):
        def wrapit(x):
            if callable(x) and not isinstance(x, CommandMakerSuperClass):
                return self.callable(x, level=callable_level)
            # otherwise
            ty = type(x)
            if ty is list:
                return list(wrapit(y) for y in x)
            if ty is tuple:
                return tuple(wrapit(y) for y in x)
            if ty is dict:
                return dict((k, wrapit(v)) for (k,v) in x.items())
            # default
            return x
        return wrapit(x)

    def wrap_callables0(self, x, callable_level=3):
        if callable(x) and not isinstance(x, CommandMakerSuperClass):
            return self.callable(x, level=callable_level)
        w = self.wrap_callables
        ty = type(x)
        if ty is list:
            return list(w(y) for y in x)
        if ty is tuple:
            return tuple(w(y) for y in x)
        if ty is dict:
            return dict((k, w(v)) for (k,v) in x.items())
        # default
        return x

    print_on_error = True

    def setTimeout(self, callable, milliseconds):
        "Convenience access to window.setTimeout in Javascript"
        self.element.window.setTimeout(callable, milliseconds)

    def on_rendered(self, callable, *positional, **keyword):
        """
        After the widget has rendered, call the callable using the provided arguments.
        This can be used to initialize an animation after the widget is visible, for example.
        """
        def call_it():
            return callable(*positional, **keyword)
        self.js_init("call_it();", call_it=call_it)

    def handle_error_msg(self, att_name, old, new):
        if self.print_on_error:
            print("new error message: " + new)

    def handle_rendered(self, att_name, old, new):
        "when rendered send any commands awaiting the render event."
        try:
            #if self.commands_awaiting_render:
                #self.send_commands([])
            if self.auto_flush:
                #("xxxx flushing on render")
                self.flush()
            self.status= "Rendered."
        except Exception as e:
            self.error_msg = repr(e)
            raise

    def send_custom_message(self, indicator, payload):
        package = { 
            INDICATOR: indicator,
            PAYLOAD: payload,
        }
        self._last_payload = payload
        if self.verbose:
            print("sending")
            pprint(package)
        #debug_check_commands(package)
        self.send(package)

    # slot for last message data debugging
    _last_message_data = None
    _json_accumulator = []
    _last_custom_message_error = None
    _last_accumulated_json = None
    
    # Output context for message handling -- will print exception traces, for example, if set
    output = None 

    def handle_custom_message_wrapper(self, widget, data, *etcetera):
        "wrapper to enable output redirects for custom messages."
        output = self.output
        if output is not None:
            with output:
                self.handle_custom_message(widget, data, *etcetera)
        else:
            self.handle_custom_message(widget, data, *etcetera)

    def debugging_display(self, tagline="debug message area for widget:", border='1px solid black'):
        if border:
            out = widgets.Output(layout={'border': border})
        else:
            out = widgets.Output()
        if tagline:
            with out:
                print (tagline)
        self.output = out
        status_text = widgets.Text(description="status:", value="")
        traitlets.directional_link((self, "status"), (status_text, "value"))
        error_text = widgets.Text(description="error", value="")
        traitlets.directional_link((self, "error_msg"), (error_text, "value"))
        assembly = widgets.VBox(children=[self, status_text, error_text, out])
        return assembly

    def handle_custom_message(self, widget, data, *etcetera):
        #pr("handle custom message")
        #pprint(data)
        try:
            self._last_message_data = data
            indicator = data[INDICATOR]
            payload = data[PAYLOAD]
            if indicator == RESULTS:
                self.results = payload
                self.status = "Got results."
                self.handle_results(payload)
            elif indicator == CALLBACK_RESULTS:
                self.status = "got callback results"
                self.last_callback_results = payload
                self.handle_callback_results(payload)
            elif indicator == JSON_CB_FRAGMENT:
                self.status = "got callback fragment"
                self._json_accumulator.append(payload)
            elif indicator == JSON_CB_FINAL:
                self.status = "got callback final"
                acc = self._json_accumulator
                self._json_accumulator = []
                acc.append(payload)
                self._last_accumulated_json = acc
                accumulated_json_str = u"".join(acc)
                accumulated_json_ob = json.loads(accumulated_json_str)
                self.handle_callback_results(accumulated_json_ob)
            else:
                self.status = "Unknown indicator from custom message " + repr(indicator)
        except Exception as e:
            # for debugging assistance
            #pr ("custom message error " + repr(e))
            self._last_custom_message_error = e
            self.error_msg = repr(e)
            raise

    def unique_id(self, prefix="jupyter_proxy_widget_id_"):
        IDENTITY_COUNTER[0] += 1
        return prefix + str(IDENTITY_COUNTER[0])

    def __call__(self, command):
        "Send command convenience."
        return self.buffer_command(command)

    def buffer_command(self, command):
        "Add a command to the buffered commands. Convenience."
        self.buffer_commands([command])
        return command

    def buffer_commands(self, commands):
        self.buffered_commands.extend(commands)
        if self.auto_flush:
            self.flush()
        return commands

    def seg_flush(self, results_callback=None, level=1, segmented=BIG_SEGMENT):
        "flush a potentially large command sequence, segmented."
        return self.flush(results_callback, level, segmented)

    error_on_flush = False  # Primarily for debugging

    def flush(self, results_callback=None, level=1, segmented=None):
        "send the buffered commands and clear the buffer. Convenience."
        if not self.rendered:
            #("XXXX not flushing before render", len(self.buffered_commands))
            self.status = "deferring flush until render"
            return None
        if self.error_on_flush:
            raise ValueError("flush is disabled")
        commands = self.buffered_commands
        self.buffered_commands = []
        #("XXXXX now flushing", len(commands))
        result = self.send_commands(commands, results_callback, level, segmented=segmented)
        self._send_counter += 1
        return result

    def save(self, name, reference):
        """
        Proxy to save referent in the element namespace by name.
        The command to save the element is buffered and the return
        value is a reference to the element by name.
        """
        elt = self.get_element()
        reference = self.wrap_callables(reference)
        save_command = elt._set(name, reference)
        # buffer the save operation
        self(save_command)
        # return the reference by name
        return getattr(self.element, name)

    _jqueryUI_checked = False

    def check_jquery(self, onsuccess=None, force=False,
        code_fn="js/jquery-ui-1.12.1/jquery-ui.js", 
        style_fn="js/jquery-ui-1.12.1/jquery-ui.css"):
        """
        Make JQuery and JQueryUI globally available for other modules.
        """
        # window.jQuery is automatically defined if absent.
        if force or not self._jqueryUI_checked:            
            self.load_js_files([code_fn])
            self.load_css(style_fn)
            # no need to load twice.
            JSProxyWidget._jqueryUI_checked = True
        if onsuccess:
            onsuccess()

    def in_dialog(
            self,
            title="",
            autoOpen=True,
            buttons=None,  # dict of label to callback
            height="auto",
            width=300,
            modal=False,
            **other_options,
        ):
        """
        Pop the widget into a floating jQueryUI dialog. See https://api.jqueryui.com/1.9/dialog
        """
        self.check_jquery()
        options = clean_dict(
            title=title,
            autoOpen=autoOpen,
            buttons=buttons,
            height=height,
            width=width,
            modal=modal,
            **other_options,
            )
        self.element.dialog(options)

    _require_checked = False
    _needs_requirejs = False
    _delayed_require_actions = None

    def uses_require(self, action=None, filepath="js/require.js"):
        """
        Force load require.js if window.require is not yet available.
        """
        # For subsequent actions wait for require to have loaded before executing
        self._needs_requirejs = True
        def load_failed():
            raise ImportError("Failed to load require.js in javascript context.")
        def require_ok():
            pass  # do nothing
        # this is a sequence of message callbacks:
        if self._require_checked:
            # if require is loaded, just do it
            self.element.alias_require(require_ok, load_failed)
            if action:
                action()
            return
        # uses_require actions should be done in order.
        # delay subsequent actions until this action is complete
        # NOTE: if communications fail this mechanism may lock up the widget.
        delayed = self._delayed_require_actions
        if delayed:
            # do this action when the previous delayed actions are complete
            # pr("delaying action because uses_require is in process")
            if action:
                delayed.append(action)
            return
        # otherwise this is the first delayed action
        if action:
            self._delayed_require_actions = [action]
        def check_require():
            "alias require/define or load it if is not available."
            # pr ("calling alias_require")
            self.element.alias_require(load_succeeded, load_require)
        def load_require():
            "load require.js and validate the load, fail on timeout"
            # pr ("loading " + filepath)
            self.load_js_files([filepath])
            # pr ("calling when loaded " + filepath)
            self.element.when_loaded([filepath], validate_require, load_failed)
        def validate_require():
            # pr ("validating require load")
            self.element.alias_require(load_succeeded, load_failed)
        def load_succeeded():
            JSProxyWidget._require_checked = True
            #if action:
            #    action()
            # execute all delayed actions in insertion order
            delayed = self._delayed_require_actions
            while delayed:
                current_action = delayed[0]
                del delayed[0]
                try:
                    current_action()
                except Exception as e:
                    self.error_msg = "require.js delayed action exception " + repr(e)
                    self._delayed_require_actions[:] = []
                    return
            self._delayed_require_actions = None
        # Start the async message sequence
        # pr ("checking require")
        check_require()

    def load_css(self, filepath, local=True):
        """
        Load a CSS text content from a file accessible by Python.
        """
        text = js_context.get_text_from_file_name(filepath, local)
        return self.load_css_text(filepath, text)

    def load_css_text(self, filepath, text):
        cmd = self.load_css_command(filepath, text)
        self(cmd)
        #return js_context.display_css(self, text)

    def require_js(self, name, filepath, local=True):
        """
        Load a require.js module from a file accessible by Python.
        Define the module content using the name in the requirejs module system.
        """
        def load_it():
            text = js_context.get_text_from_file_name(filepath, local)
            return self.load_js_module_text(name, text)
        self.uses_require(load_it)

    def load_js_module_text(self, name, text):
        """
        Load a require.js module text.
        """
        return self.element._load_js_module(name, text);
        #elt = self.get_element()
        #load_call = elt._load_js_module(name, text)
        #self(load_call)
        # return reference to the loaded module
        #return getattr(elt, name)

    def save_new(self, name, constructor, arguments):
        """
        Construct a 'new constructor(arguments)' and save in the element namespace.
        Store the construction in the command buffer and return a reference to the
        new object.
        This must be followed by a flush() to execute the command.
        """
        new_reference = self.get_element().New(constructor, arguments)
        return self.save(name, new_reference)

    def save_function(self, name, arguments, body):
        """
        Buffer a command to create a JS function using "new Function(...)"
        """
        klass = self.window().Function
        return self.save_new(name, klass, list(arguments) + [body])

    def function(self, arguments, body):
        klass = self.window().Function
        return self.get_element().New(klass, list(arguments) + [body])

    handle_results_exception = None

    def handle_results(self, new):
        "Callback for when results arrive after the JS View executes commands."
        if self.verbose:
            print ("got results", new)
        [identifier, json_value] = new
        i2c = self.identifier_to_callback
        results_callback = i2c.get(identifier)
        if results_callback is not None:
            del i2c[identifier]
            try:
                results_callback(json_value)
            except Exception as e:
                #pr ("handle results exception " + repr(e))
                self.handle_results_exception = e
                self.error_msg = "Handle results: " + repr(e)
                raise

    handle_callback_results_exception = None
    last_callback_results = None

    def handle_callback_results(self, new):
        "Callback for when the JS View sends an event notification."
        #pr ("HANDLE CALLBACK RESULTS")
        #pprint(new)
        self.last_callback_results = new
        if self.verbose:
            print ("got callback results", new)
        [identifier, json_value, arguments, counter] = new
        i2c = self.identifier_to_callback
        results_callback = i2c.get(identifier)
        self.status = "call back to " + repr(results_callback)
        if results_callback is not None:
            try:
                results_callback(json_value, arguments)
            except Exception as e:
                #pr ("handle results callback exception " +repr(e))
                self.handle_callback_results_exception = e
                self.error_msg = "Handle callback results: " + repr(e)
                raise

    def send_command(self, command, results_callback=None, level=1):
        "Send a single command to the JS View."
        return self.send_commands([command], results_callback, level)

    def send_commands(self, commands_iter, results_callback=None, level=1, segmented=None, check=False):
        """Send several commands fo the JS View.
        If segmented is a positive integer then the commands payload will be pre-encoded
        as a json string and sent in segments of that length
        """
        count = self.counter
        self.counter = count + 1
        commands_iter = list(commands_iter)
        qcommands = list(map(quoteIfNeeded, commands_iter))
        commands = self.validate_commands(qcommands)
        if check:
            debug_check_commands(commands)
        if self.rendered:
            # also send buffered commands
            #if self.commands_awaiting_render:
            #    commands = commands + self.commands_awaiting_render
            #    self.commands_awaiting_render = None
            if self.buffered_commands:
                commands = self.buffered_commands + commands
                self.buffered_commands = []
            payload = [count, commands, level]
            if results_callback is not None:
                self.identifier_to_callback[count] = results_callback
            # send the command using the commands traitlet which is mirrored to javascript.
            #self.commands = payload
            if segmented and segmented > 0:
                self.send_segmented_message(COMMANDS_FRAGMENT, COMMANDS_FINAL, payload, segmented)
            else:
                self.send_custom_message(COMMANDS, payload)
            self.last_commands_sent = payload
            return payload
        else:
            # wait for render event before sending commands.
            ##pr "waiting for render!", commands
            #self.commands_awaiting_render.extend(commands)
            self.buffered_commands.extend(commands)
            return ("awaiting render", commands)

    def send_segmented_message(self, frag_ind, final_ind, payload, segmented):
        "Send a message in fragments."
        json_str = json.dumps(payload)
        len_json = len(json_str)
        cursor = 0
        # don't reallocate large string tails...
        while len_json - cursor > segmented:
            next_cursor = cursor + segmented
            json_fragment = json_str[cursor: next_cursor]
            # send the fragment
            self.send_custom_message(frag_ind, json_fragment)
            cursor = next_cursor
        json_tail = json_str[cursor:]
        self.send_custom_message(final_ind, json_tail)

    _synced_command_result = None
    _synced_command_evaluated = False
    _synced_command_timed_out = False
    _synced_command_timeout_time = None

    def evaluate(self, command, level=3, timeout=3000, ms_delay=100):
        "Evaluate the command and return the converted javascript value."
        # temporarily disable error prints
        print_on_error = self.print_on_error
        old_err = self.error_msg
        try:
            # Note: if the command buffer has not been flushed other operations may set the error_msg
            self.print_on_error = False
            self.error_msg = ""
            self._synced_command_result = None
            self._synced_command_timed_out = False
            self._synced_command_evaluated = False
            self._synced_command_timeout_time = None
            start = time.time()
            if timeout is not None and timeout > 0:
                self._synced_command_timeout_time = start + timeout
            start = self._synced_command_start_time = time.time()
            self._send_synced_command(command, level, ms_delay=ms_delay)
            run_ui_poll_loop(self._sync_complete)
            if self._synced_command_timed_out:
                raise TimeoutError("wait: %s, started: %s; gave up %s" % (timeout, start, time.time()))
            assert self._synced_command_evaluated, repr((self._synced_command_evaluated, self._synced_command_result))
            error_msg = self.error_msg
            result = self._synced_command_result
            if error_msg:
                if error_msg == result:
                    raise JavascriptException("sync error: " + repr(error_msg))
                else:
                    old_err = error_msg
            return result
        finally:
            # restore error prints if formerly enabled
            self.error_msg = old_err
            self.print_on_error = print_on_error

    def _send_synced_command(self, command, level, ms_delay=100):
        if self.last_fragile_reference is not command:
            set_ref = SetMaker(self.get_element(), FRAGILE_JS_REFERENCE, command)
            self.buffer_command(set_ref)
        #self.element._SEND_FRAGILE_JS_REFERENCE()
        get_ref = CallMaker("method", self.get_element(), SEND_FRAGILE_JS_REFERENCE, ms_delay)
        self.buffer_command(get_ref)
        self.flush()

    def _RECEIVE_FRAGILE_REFERENCE(self, value):
        self._synced_command_result = value
        self._synced_command_evaluated = True

    def _sync_complete(self):
        if self._synced_command_timeout_time is not None:
            self._synced_command_timed_out = (time.time() > self._synced_command_timeout_time)
        test = self._synced_command_evaluated or self._synced_command_timed_out
        if test:
            return test
        else:
            return None  # only None signals end of polling loop.
    
    """ # doesn't work: not used.
    def evaluate(self, command, level=1, timeout=3000):
        "Send one command and wait for result.  Return result."
        results = self.evaluate_commands([command], level, timeout)
        assert len(results) == 1
        return results[0]

    def evaluate_commands(self, commands_iter, level=1, timeout=3000):
        "Send commands and wait for results.  Return results."
        # inspired by https://github.com/jdfreder/ipython-jsobject/blob/master/jsobject/utils.py
        result_list = []

        def evaluation_callback(json_value):
            result_list.append(json_value)

        self.send_commands(commands_iter, evaluation_callback, level)
        # get_ipython is a builtin in the ipython context (no import needed (?))
        #ip = get_ipython()
        start = time.time()
        while not result_list:
            if time.time() - start > timeout/ 1000.0:
                raise Exception("Timeout waiting for command results: " + repr(timeout))
            ip.kernel.do_one_iteration()
        return result_list[0]
    """

    def seg_callback(self, callback_function, data, level=1, delay=False, segmented=BIG_SEGMENT):
        """
        Proxy callback with message segmentation to support potentially large
        messages.
        """
        return self.callback(callback_function, data, level, delay, segmented)

    def callable(self, function_or_method, level=1, delay=False, segmented=None):
        """
        Simplified callback protocol.
        Map function_or_method to a javascript function js_function
        Calls to js_function(x, y, z)
        will trigger calls to function_or_method(x, y, z)
        where x, y, z are json compatible values.
        """
        # do not double wrap CallMakers
        if isinstance(function_or_method, CallMaker):
            return function_or_method
        # get existing wrapper value from cache, if available
        cache = self.callable_cache
        result = cache.get(function_or_method)
        if result is not None:
            return result
        data = repr(function_or_method)
        def callback_function(_data, arguments):
            count = 0
            # construct the Python argument list from argument mapping
            py_arguments = []
            while 1:
                argstring = str(count)
                if argstring in arguments:
                    argvalue = arguments[argstring]
                    py_arguments.append(argvalue)
                    count += 1
                else:
                    break
            function_or_method(*py_arguments)
        result = self.callback(callback_function, data, level, delay, segmented)
        cache[function_or_method] = result
        return result

    def callback(self, callback_function, data, level=1, delay=False, segmented=None):
        "Create a 'proxy callback' to receive events detected by the JS View."
        assert level > 0, "level must be positive " + repr(level)
        assert level <= 5, "level cannot exceed 5 " + repr(level)
        assert segmented is None or (type(segmented) is int and segmented > 0), "bad segment " + repr(segmented)
        count = self.counter
        self.counter = count + 1
        assert not isinstance(callback_function, CommandMakerSuperClass), "can't callback command maker " + type(callback_function)
        assert not str(data).startswith("Fragile"), "DEBUG::" + repr(data)
        command = CallMaker("callback", count, data, level, segmented)
        #if delay:
        #    callback_function = delay_in_thread(callback_function)
        self.identifier_to_callback[count] = callback_function
        return command

    def forget_callback(self, callback_function):
        "Remove all uses of callback_function in proxy callbacks (Python side only)."
        i2c = self.identifier_to_callback
        deletes = [i for i in i2c if i2c[i] == callback_function]
        for i in deletes:
            del i2c[i]

    def js_debug(self, *arguments):
        """
        Break in the Chrome debugger (only if developer tools is open)
        """
        if not arguments:
            arguments = [self.get_element()]
        return self.send_command(self.function(["element"], "debugger;")(self.get_element()))

    def print_status(self):
        status_slots = """
            results
            auto_flush _last_message_data _json_accumulator _last_custom_message_error
            _last_accumulated_json _jqueryUI_checked _require_checked
            handle_results_exception last_callback_results
            """
        print (repr(self) + " STATUS:")
        for slot_name in status_slots.split():
            print ("\t::::: " + slot_name + " :::::")
            print (getattr(self, slot_name, "MISSING"))

    def get_element(self):
        "Return a proxy reference to the Widget JQuery element this.$el."
        return CommandMaker("element")

    def window(self):
        "Return a proxy reference to the browser window top level name space."
        return CommandMaker("window")

    def load_js_files(self, filenames, force=True, local=True):
        for filepath in filenames:
            def load_the_file(filepath=filepath):
                # pr ("loading " + filepath)
                filetext = js_context.get_text_from_file_name(filepath, local=True)
                cmd = self.load_js_command(filepath, filetext)
                self(cmd)
            if force:
                # this may result in reading and sending the file content too many times...
                load_the_file()
            else:
                # only load the file if no file of that name has been loaded
                load_callback = self.callable(load_the_file)
                # pr ("test/loading " + filepath + " " + repr(load_callback))
                self.element.test_js_loaded([filepath], None, load_callback)

    def load_js_command(self, js_name, js_text):
        return Loader(LOAD_JS, js_name, js_text)

    def load_css_command(self, css_name, css_text):
        return Loader(LOAD_CSS, css_name, css_text)


    def validate_commands(self, commands, top=True):
        """
        Validate a command sequence (and convert to list format if needed.)
        """
        return [self.validate_command(c, top) for c in commands]

    def validate_command(self, command, top=True):
        # convert CommandMaker to list format.
        if isinstance(command, CommandMakerSuperClass):
            command = command._cmd()
        elif callable(command):
            # otherwise convert callables to callbacks, in list format
            command = self.callable(command)._cmd()
        assert not isinstance(command, CommandMakerSuperClass), repr((type(command), command))
        ty = type(command)
        if ty is list:
            indicator = command[0]
            remainder = command[1:]
            if indicator == "element" or indicator == "window":
                assert len(remainder) == 0
            elif indicator == "method":
                target = remainder[0]
                name = remainder[1]
                args = remainder[2:]
                target = self.validate_command(target, top=True)
                assert type(name) is str, "method name must be a string " + repr(name)
                args = self.validate_commands(args, top=False)
                remainder = [target, name] + args
            elif indicator == "function":
                target = remainder[0]
                args = remainder[1:]
                target = self.validate_command(target, top=True)
                args = self.validate_commands(args, top=False)
                remainder = [target] + args
            elif indicator == "id" or indicator == "bytes":
                assert len(remainder) == 1, "id or bytes takes one argument only " + repr(remainder)
            elif indicator in LOAD_INDICATORS:
                assert len(remainder) == 2, "loaders take exactly 2 arguments" + repr(len(remainder))
            elif indicator == "list":
                remainder = self.validate_commands(remainder, top=False)
            elif indicator == "dict":
                [d] = remainder
                d = dict((k, self.validate_command(d[k], top=False)) for k in d)
                remainder = [d]
            elif indicator == "callback":
                [numerical_identifier, untranslated_data, level, segmented] = remainder
                assert type(numerical_identifier) is int, \
                    "must be integer " + repr(numerical_identifier)
                assert type(level) is int, \
                    "must be integer " + repr(level)
                assert (segmented is None) or (type(segmented) is int and segmented > 0), \
                    "must be None or positive integer " + repr(segmented)
            elif indicator == "get":
                [target, name] = remainder
                target = self.validate_command(target, top=True)
                name = self.validate_command(name, top=False)
                remainder = [target, name]
            elif indicator == "set":
                [target, name, value] = remainder
                target = self.validate_command(target, top=True)
                name = self.validate_command(name, top=False)
                value = self.validate_command(value, top=False)
                remainder = [target, name, value]
            elif indicator == "null":
                [target] = remainder
                remainder = [self.validate_command(target, top=False)]
            else:
                raise ValueError("bad indicator " + repr(indicator))
            command = [indicator] + remainder
        elif top:
            raise ValueError("top level command must be a list " + repr(command))
        # Non-lists are untranslated (but should be JSON compatible).
        return command

    def delay_flush(self):
        """
        Context manager to group a large number of operations into one message.
        This can prevent flooding messages over the ZMQ communications link between
        the Javascript front end and the Python kernel backend.

        >>> with widget.delay_flush():
        ...    many_operations(widget)
        ...    even_more_operations(widget)
        """
        return DisableFlushContextManager(self)

def indent_string(s, level, indent="    "):
    lindent = indent * level
    return s.replace("\n", "\n" + lindent)

def to_javascript(thing, level=0, indent=None, comma=","):
    if isinstance(thing, CommandMakerSuperClass):
        result = thing.javascript(level)
    else:
        ty = type(thing)
        json_value = None
        if ty is dict:
            L = {"%s: %s" % (to_javascript(key), to_javascript(thing[key]))
                for key in thing.keys()}
            json_value = "{%s}" % (comma.join(L))
        elif ty is list or ty is tuple:
            L = [to_javascript(x) for x in thing]
            json_value = "[%s]" % (comma.join(L))
        elif ty is bytearray:
            inner = list(map(int, thing))
            # Note: no line breaks for binary data.
            json_value = "Uint8Array(%s)" % inner
        elif json_value is None:
            json_value = json.dumps(thing, indent=indent)
        result = indent_string(json_value, level)
    assert type(result) is str, repr((thing, result))
    return result


# Adapted from jp_doodle.dual_canvas.DisableRedrawContextManager

class DisableFlushContextManager(object):
    """
    Temporarily disable flushes and also collect widget messages into a single group.
    This can speed up widget interactions and prevent the communication channel from flooding.
    """

    def __init__(self, canvas):
        self.canvas = canvas
        self.save_flush = canvas.auto_flush

    def __enter__(self):
        canvas = self.canvas
        self.save_flush = canvas.auto_flush
        canvas.auto_flush = False

    def __exit__(self, type, value, traceback):
        canvas = self.canvas
        canvas.auto_flush = self.save_flush
        if (self.save_flush):
            canvas.flush()


class ElementWrapper(object):

    """
    Convenient top level access to the widget element.

    widget.element.action_name(arg1, arg2)

    executes the same as widget(widget.get_element.action_name(arg1, arg2))
    which executes this.$$el.action_name(arg1, arg2) on the Javascript side.
    """

    def __init__(self, for_widget):
        assert isinstance(for_widget, JSProxyWidget)
        self.widget = for_widget
        self.widget_element = for_widget.get_element()

    def __getattr__(self, name):
        #return ElementCallWrapper(self.widget, self.widget_element, name)
        if name == '_ipython_canary_method_should_not_exist_':
            return 42  # ipython poking around...
        return LazyGet(self.widget, self.widget_element, name)

    # for parallelism to _set
    _get = __getattr__

    # in javascript these are essentially the same thing.
    __getitem__ = __getattr__

    def _set(self, name, value):
        "Proxy to set a property of the widget element."
        #return self.widget(self.widget_element._set(name, value))
        ref = value
        if isinstance(value, CommandMakerSuperClass):
            ref = value.reference()
        command = SetMaker(self.widget_element, name, ref)
        self.widget.buffer_commands([command])
        return LazyGet(self.widget, self.widget_element, name)

class StaleFragileJavascriptReference(ValueError):
    "Stale Javascript value reference"

class CommandMakerSuperClass(object):
    """
    Superclass for command proxy objects.
    """
    def reference(self):
        "return cached value if available"
        return self # default -- not cached

class LazyCommandSuperClass(CommandMakerSuperClass):

    fragile_reference = "invalid"

    def __repr__(self):
        return repr(self._cmd())

    def reference(self):
        for_widget = self.for_widget
        if for_widget.last_fragile_reference is self:
            #return this.fragile_reference
            return MethodMaker(for_widget.get_element(), FRAGILE_JS_REFERENCE)
        else:
            return self

    def this_reference(self):
        raise ValueError("this_reference only makes sense for Get")

    def javascript(self, *args):
        raise NotImplementedError("don't convert lazy commands to javascript for now.")
        #return repr("Javascript disabled for lazy commands: " + repr(type(self)))

    def __getattr__(self, attribute):
        if type(attribute) is str and '_ipython' in attribute:
            return "attributes mentioning _ipython are forbidden because they cause infinite recursions: " + repr(attribute)
        return LazyGet(self.for_widget, self, attribute)

    def __getitem__(self, item):
        return self.__getattr__(item)

    def __call__(self, *args):
        return LazyCall(self.for_widget, self, *args)

    def _cmd(self):
        raise NotImplementedError("_cmd must be defined in subclass")

    def method(self, name):
        def result(*args):
            f = getattr(self, name)
            return f(*args)
        return result

    def sync_value(self, timeout=3000, level=3, ms_delay=100):
        """
        Return the converted javascript-side value for this command.
        """
        for_widget = self.for_widget
        for_widget.evaluate(self, timeout=timeout, level=level, ms_delay=ms_delay)
        return for_widget._synced_command_result


class LazyGet(LazyCommandSuperClass):

    def __init__(self, for_widget, for_target, attribute):
        self.for_target = for_target
        self.for_widget = for_widget
        self.attribute = attribute
        # when executing immediately put target ref in fragile_this and attr value in fragile_ref
        set_this = SetMaker(for_widget.get_element(), FRAGILE_THIS, for_target.reference())
        # get attr value as element.fragile_this.attr
        attr_ref = MethodMaker(MethodMaker(for_widget.get_element(), FRAGILE_THIS), attribute)
        set_ref = SetMaker(for_widget.get_element(), FRAGILE_JS_REFERENCE, attr_ref)
        # execute immediately on init
        for_widget.buffer_commands([set_this, set_ref])
        # use fragile ref to find value, until the cached value is replaced
        for_widget.last_fragile_reference = self

    def _cmd(self):
        m = MethodMaker(self.for_target, self.attribute)
        return m._cmd()

    def __call__(self, *args):
        if type(self.attribute) is str:
            return LazyMethodCall(self.for_widget, self, *args)
        else:
            m = MethodMaker(self.for_target, self.attribute)
            return LazyCall(self.for_widget, m, *args)

    def this_reference(self):
        for_widget = self.for_widget
        if for_widget.last_fragile_reference is self:
            #return this.fragile_reference
            return MethodMaker(for_widget.get_element(), FRAGILE_THIS)
        else:
            return self.for_target

class LazyCall(LazyCommandSuperClass):

    def __init__(self, for_widget, for_target, *args):
        self.for_target = for_target
        self.for_widget = for_widget
        args = for_widget.wrap_callables(args)
        self.args = args
        # when executing immediately save result of call in fragile_ref
        set_ref = SetMaker(
            for_widget.get_element(),
            FRAGILE_JS_REFERENCE,
            CallMaker("function", self.for_target.reference(), *args)
        )
        for_widget.buffer_commands([set_ref])
        for_widget.last_fragile_reference = self

    def _cmd(self):
        c = CallMaker("function", self.for_target, *self.args)
        return c.cmd()
        
class LazyMethodCall(LazyCommandSuperClass):

    def __init__(self, for_widget, for_method, *args):
        self.for_method = for_method
        self.for_widget = for_widget
        args = for_widget.wrap_callables(args)
        self.args = args
        # when executing immediately save result of call in fragile_ref
        set_ref = SetMaker(
            for_widget.get_element(),
            FRAGILE_JS_REFERENCE,
            CallMaker("method", for_method.this_reference(), for_method.attribute, *args)
        )
        for_widget.buffer_commands([set_ref])
        for_widget.last_fragile_reference = self

    def _cmd(self):
        for_method = self.for_method
        m = CallMaker("method", for_method.for_target, for_method.attribute, *self.args)
        return m._cmd()

class CommandMaker(CommandMakerSuperClass):

    """
    Superclass for command proxy objects.
    Directly implements top level objects like "window" and "element".
    """

    top_level_names = "window element".split()

    def __init__(self, name="window"):
        assert name in self.top_level_names
        self.name = name

    def __repr__(self):
        #return self.javascript()
        return repr(type(self)) + "::" + repr(id(self))   # disable informative reprs for now

    def javascript(self, level=0):
        "Return javascript text intended for this command"
        return indent_string(self.name, level)
    
    def _cmd(self):
        "Translate self to JSON representation for transmission to view."
        return [self.name]

    def __getattr__(self, name):
        "Proxy to get a property of a jS object."
        return MethodMaker(self, name)

    # for parallelism to _set
    _get = __getattr__

    # in javascript these are essentially the same thing.
    __getitem__ = __getattr__

    def _set(self, name, value):
        "Proxy to set a property of a JS object."
        return SetMaker(self, name, value)

    def __call__(self, *args):
        "Proxy to call a JS object."
        raise ValueError("top level object cannot be called.")

    def _null(self):
        "Proxy to discard results of JS evaluation."
        return ["null", self]


# For attribute access use target[value] instead of target.name
# because sometimes the value will not be a string.


Set_Template = """
f = function () {
    var target = %s;
    var attribute = %s;
    var value = %s;
    target[attribute] = value;
    return target;
};
f();
""".strip()


class SetMaker(CommandMaker):
    """
    Proxy container to set target.name = value.
    """

    def __init__(self, target, name, value):
        self.target = target
        self.name = name
        self.value = value

    def javascript(self, level=0):
        innerlevel = 2
        target = to_javascript(self.target, innerlevel)
        value = to_javascript(self.value, innerlevel)
        name = to_javascript(self.name, innerlevel)
        T = Set_Template % (target, name, value)
        return indent_string(T, level)

    def _cmd(self):
        #target = validate_command(self.target, False)
        #@value = validate_command(self.value, False)
        target = self.target
        value = self.value
        return ["set", target, self.name, value]


class Loader(CommandMaker):
    """
    Special commands for loading css and js async.
    """

    def __init__(self, indicator, name, text_content):
        assert indicator in LOAD_INDICATORS
        self.indicator = indicator
        self.name = name
        self.text_content = text_content

    def javascript(self, level=0):
        raise NotImplementedError("this hasn't been implemented yet, sorry.")

    def _cmd(self):
        return [self.indicator, self.name, self.text_content]


class MethodMaker(CommandMaker):
    """
    Proxy reference to a property or method of a JS object.
    """

    def __init__(self, target, name):
        self.target = target
        self.name = name

    def javascript(self, level=0):
        # use target[value] notation (see comment above)
        target = to_javascript(self.target)
        attribute = to_javascript(self.name)
        # add a line break in case of long chains
        T = "%s\n[%s]" % (target, attribute)
        return indent_string(T, level)

    def _cmd(self):
        #target = validate_command(self.target, False)
        target = self.target
        return ["get", target, self.name]

    def __call__(self, *args):
        return CallMaker("method", self.target, self.name, *args)



def format_args(args):
    args_js = [to_javascript(a, 1) for a in args]
    args_inner = ",\n".join(args_js)
    return "(%s)" % args_inner


class CallMaker(CommandMaker):
    """
    Proxy reference to a JS method call or function call.
    If kind == "method" and args == [target, name, arg0, ..., argn]
    Then proxy value is target.name(arg0, ..., argn)
    """

    def __init__(self, kind, *args):
        self.kind = kind
        self.args = quoteLists(args)

    def javascript(self, level=0):
        kind = self.kind
        args = self.args
        # Add newlines in case of long chains.
        if kind == "function":
            function_desc = args[0]
            function_args = [to_javascript(x) for x in args[1:]]
            function_value = to_javascript(function_desc)
            call_js = "%s\n%s" % (function_value, format_args(function_args))
            return indent_string(call_js, level)
        elif kind == "method":
            target_desc = args[0]
            name = args[1]
            method_args = [to_javascript(x) for x in args[2:]]
            target_value = to_javascript(target_desc)
            name_value = to_javascript(name)
            method_js = "%s\n[%s]\n%s" % (target_value, name_value, format_args(method_args))
            return indent_string(method_js, level)
        else:
            # This should never be executed, but the javascript
            # translation is useful for debugging.
            message = "Warning: External callable " + repr(self.args)
            return "function() {alert(%s);}" % to_javascript(message)

    def __call__(self, *args):
        """
        Call the callable returned by the function or method call.
        """
        return CallMaker("function", self, *args)

    def _cmd(self):
        return [self.kind] + self.args #+ validate_commands(self.args, False)


def np_array_to_list(a):
    return a.tolist()


class LiteralMaker(CommandMaker):
    """
    Proxy to make a literal dictionary or list which may contain other
    proxy references.
    """

    translators = {
        np.ndarray: np_array_to_list,
        #np.float: float,
        #np.float128: float,
        #np.float16: float,
        #np.float32: float,
        #np.float64: float,
        #np.int: int,
        #np.int0: int,
        #np.int16: int,
        #np.int32: int,
        #np.int64: int,
    }
    for type_name in "float float128 float16 float32 float64".split():
        if hasattr(np, type_name):
            ty = getattr(np, type_name)
            translators[ty] = float
    for type_name in "int int0 int16 int32 int64".split():
        if hasattr(np, type_name):
            ty = getattr(np, type_name)
            translators[ty] = int

    indicators = {
        # things we can translate
        dict: "dict", list: "list", bytearray: "bytes",
        # we can't translate non-specific types, modules, etc.
        type: "don't translate non-specific types, like classes",
        type(json): "don't translate modules",
        # xxxx should improve sanity checking on types...
        }

    def __init__(self, thing):
        self.thing = thing

    def javascript(self, level=0):
        thing_fmt = to_javascript(self.thing)
        return indent_string(thing_fmt, level)

    def _cmd(self):
        thing = self.thing
        ty = type(thing)
        indicator = self.indicators.get(ty)
        #return [indicator, thing]
        if indicator:
            # exact type equality here:
            if ty is list:
                return [indicator] + quoteLists(thing)
            elif ty is dict:
                return [indicator, dict((k, quoteIfNeeded(thing[k])) for k in thing)]
            elif ty is bytearray:
                return [indicator, bytearray_to_hex(thing)]
            else:
                raise ValueError("can't translate " + repr(ty))
        return thing


def quoteIfNeeded(arg):
    ty = type(arg)
    translator = LiteralMaker.translators.get(ty)
    if translator:
        arg = translator(arg)
        ty = type(arg)
    if ty in LiteralMaker.indicators:
        return LiteralMaker(arg)
    return arg

def quoteLists(args):
    "Wrap lists or dictionaries in the args in LiteralMakers"
    return [quoteIfNeeded(x) for x in args]


class InvalidCommand(Exception):
    "Invalid command"


def debug_check_commands(command):
    "raise an error if the command is not a basic json structure"
    if command is None:
        return command
    ty = type(command)
    if ty in (int, float, str,  bool):
        return command
    if ty in (tuple, list):
        result = command
        for x in command:
            result = debug_check_commands(x)
        return result
    if ty is dict:
        return debug_check_commands(list(command.items()))
    # otherwise
    raise InvalidCommand(repr(command))



def clean_dict(**kwargs):
    "Like dict but with no None values and make some values JSON serializable."
    # This function is generally useful for passing information to proxy widgets
    result = {}
    for kw in kwargs:
        v = kwargs[kw]
        if v is not None:
            if isinstance(v, np.ndarray):
                # listiffy arrays -- maybe should be done elsewhere
                v = v.tolist()
            if isinstance(v, np.floating):
                v = float(v)
            if type(v) is tuple:
                v = list(v)
            result[kw] = v
    return result


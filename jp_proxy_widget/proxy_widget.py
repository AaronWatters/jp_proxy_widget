
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

# In the IPython context get_ipython is a builtin.
# get a reference to the IPython notebook object.
ip = IPython.get_ipython()

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

# Message segmentation size default
BIG_SEGMENT = 1000000

@widgets.register
class JSProxyWidget(widgets.DOMWidget):
    """Introspective javascript proxy widget."""
    _view_name = Unicode('JSProxyView').tag(sync=True)
    _model_name = Unicode('JSProxyModel').tag(sync=True)
    _view_module = Unicode('jp_proxy_widget').tag(sync=True)
    _model_module = Unicode('jp_proxy_widget').tag(sync=True)
    _view_module_version = Unicode('^0.3.4').tag(sync=True)
    _model_module_version = Unicode('^0.3.4').tag(sync=True)

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
        #self.callback_to_identifier = {}
        #self.on_trait_change(self.handle_callback_results, "callback_results")
        #self.on_trait_change(self.handle_results, "results")
        self.on_trait_change(self.handle_rendered, "rendered")
        self.on_trait_change(self.handle_error_msg, "error_msg")
        ##pr "registered on_msg(handle_custom_message)"
        self.on_msg(self.handle_custom_message_wrapper)
        self.buffered_commands = []
        self.commands_awaiting_render = []
        self.last_commands_sent = []
        self.last_callback_results = None
        self.results = []
        self.status = "Not yet rendered"

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
            if callable(v):
                return self.callable(v, level=callable_level)
            return listiffy(v)
        other_argument_values = [map_value(other_arguments[name]) for name in other_argument_names]
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

    print_on_error = True

    def handle_error_msg(self, att_name, old, new):
        if self.print_on_error:
            print("new error message: " + new)

    def handle_rendered(self, att_name, old, new):
        "when rendered send any commands awaiting the render event."
        try:
            if self.commands_awaiting_render:
                self.send_commands([])
            self.status= "Rendered."
        except Exception as e:
            self.error_msg = repr(e)
            raise

    def send_custom_message(self, indicator, payload):
        package = { 
            INDICATOR: indicator,
            PAYLOAD: payload,
        }
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
        try:
            self._last_message_data = data
            indicator = data[INDICATOR];
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
        "Add a command to the buffered commands. Convenience."
        self.buffered_commands.append(command)
        if self.auto_flush:
            self.flush()
        return command

    def seg_flush(self, results_callback=None, level=1, segmented=BIG_SEGMENT):
        "flush a potentially large command sequence, segmented."
        return self.flush(results_callback, level, segmented)

    def flush(self, results_callback=None, level=1, segmented=None):
        "send the buffered commands and clear the buffer. Convenience."
        commands = self.buffered_commands
        self.buffered_commands = []
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
        save_command = elt._set(name, reference)
        # buffer the save operation
        self(save_command)
        # return the reference by name
        return getattr(elt, name)

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

    def send_commands(self, commands_iter, results_callback=None, level=1, segmented=None):
        """Send several commands fo the JS View.
        If segmented is a positive integer then the commands payload will be pre-encoded
        as a json string and sent in segments of that length
        """
        count = self.counter
        self.counter = count + 1
        qcommands = list(map(quoteIfNeeded, commands_iter))
        commands = validate_commands(qcommands)
        if self.rendered:
            # also send any commands awaiting the render event.
            if self.commands_awaiting_render:
                commands = commands + self.commands_awaiting_render
                self.commands_awaiting_render = None
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
            self.commands_awaiting_render.extend(commands)
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
        return self.callback(callback_function, data, level, delay, segmented)

    def callback(self, callback_function, data, level=1, delay=False, segmented=None):
        "Create a 'proxy callback' to receive events detected by the JS View."
        assert level > 0, "level must be positive " + repr(level)
        assert level <= 5, "level cannot exceed 5 " + repr(level)
        assert segmented is None or (type(segmented) is int and segmented > 0), "bad segment " + repr(segmented)
        count = self.counter
        self.counter = count + 1
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
        #  xxxx  Use that.$$el.test_js_loaded to only load the module if needed when force is False
        #import js_context
        #js_context.load_if_not_loaded(self, filenames, verbose=verbose, delay=delay, force=force, local=local)
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


def validate_commands(commands, top=True):
    """
    Validate a command sequence (and convert to list format if needed.)
    """
    return [validate_command(c, top) for c in commands]


def validate_command(command, top=True):
    # convert CommandMaker to list format.
    if isinstance(command, CommandMaker):
        command = command._cmd()
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
            target = validate_command(target, top=True)
            assert type(name) is str, "method name must be a string " + repr(name)
            args = validate_commands(args, top=False)
            remainder = [target, name] + args
        elif indicator == "function":
            target = remainder[0]
            args = remainder[1:]
            target = validate_command(target, top=True)
            args = validate_commands(args, top=False)
            remainder = [target] + args
        elif indicator == "id" or indicator == "bytes":
            assert len(remainder) == 1, "id or bytes takes one argument only " + repr(remainder)
        elif indicator in LOAD_INDICATORS:
            assert len(remainder) == 2, "loaders take exactly 2 arguments" + repr(len(remainder))
        elif indicator == "list":
            remainder = validate_commands(remainder, top=False)
        elif indicator == "dict":
            [d] = remainder
            d = dict((k, validate_command(d[k], top=False)) for k in d)
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
            target = validate_command(target, top=True)
            name = validate_command(name, top=False)
            remainder = [target, name]
        elif indicator == "set":
            [target, name, value] = remainder
            target = validate_command(target, top=True)
            name = validate_command(name, top=False)
            value = validate_command(value, top=False)
            remainder = [target, name, value]
        elif indicator == "null":
            [target] = remainder
            remainder = [validate_command(target, top=False)]
        else:
            raise ValueError("bad indicator " + repr(indicator))
        command = [indicator] + remainder
    elif top:
        raise ValueError("top level command must be a list " + repr(command))
    # Non-lists are untranslated (but should be JSON compatible).
    return command

def indent_string(s, level, indent="    "):
    lindent = indent * level
    return s.replace("\n", "\n" + lindent)

def to_javascript(thing, level=0, indent=None, comma=","):
    if isinstance(thing, CommandMaker):
        return thing.javascript(level)
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
        return indent_string(json_value, level)


class ElementWrapper(object):

    """
    Convenient top level access to the widget element.

    widget.element.action_name(arg1, arg2)

    executes the same as widget(widget.get_element.action_name(arg1, arg2))
    which executes this.$$el.action_name(arg1, arg2) on the Javascript side.
    """

    def __init__(self, for_widget):
        self.widget = for_widget
        self.widget_element = for_widget.get_element()

    def __getattr__(self, name):
        return ElementCallWrapper(self.widget, self.widget_element, name)

    # for parallelism to _set
    _get = __getattr__

    # in javascript these are essentially the same thing.
    __getitem__ = __getattr__

    def _set(self, name, value):
        "Proxy to set a property of the widget element."
        return self.widget(self.widget_element._set(name, value))

class ElementCallWrapper(object):

    callable_level = 2   # ???

    def __init__(self, for_widget, for_element, slot_name):
        self.widget = for_widget
        self.element = for_element
        self.slot_name = slot_name
    
    def map_value(self, v):
        widget = self.widget
        if callable(v):
            return widget.callable(v, level=self.callable_level)
        return v

    def __call__(self, *args):
        mapped_args = map(self.map_value, args)
        widget = self.widget
        element = self.element
        slot = element[self.slot_name]
        widget(slot(*mapped_args))
        # Allow chaining (may not be consistent with javascript semantics)
        return element

    def __getattr__(self, name):
        for_element = self.element[self.slot_name]
        return ElementCallWrapper(self.widget, for_element, name)

    # getattr and getitem are the same in Javascript
    __getitem__ = __getattr__


class CommandMaker(object):

    """
    Superclass for command proxy objects.
    Directly implements top level objects like "window" and "element".
    """

    top_level_names = "window element".split()

    def __init__(self, name="window"):
        assert name in self.top_level_names
        self.name = name

    def __repr__(self):
        return self.javascript()

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
    For chaining the result is a reference to the target.
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
            function_args = args[1:]
            function_value = to_javascript(function_desc)
            call_js = "%s\n%s" % (function_value, format_args(function_args))
            return indent_string(call_js, level)
        elif kind == "method":
            target_desc = args[0]
            name = args[1]
            method_args = args[2:]
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


class LiteralMaker(CommandMaker):
    """
    Proxy to make a literal dictionary or list which may contain other
    proxy references.
    """

    indicators = {dict: "dict", list: "list", bytearray: "bytes"}

    def __init__(self, thing):
        self.thing = thing

    def javascript(self, level=0):
        thing_fmt = to_javascript(self.thing)
        return indent_string(thing_fmt, level)

    def _cmd(self):
        thing = self.thing
        ty = type(thing)
        indicator = self.indicators.get(type(thing))
        #return [indicator, thing]
        if indicator:
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
    if type(arg) in LiteralMaker.indicators:
        return LiteralMaker(arg)
    return arg

def quoteLists(args):
    "Wrap lists or dictionaries in the args in LiteralMakers"
    return [quoteIfNeeded(x) for x in args]



"""
This is an implementation of a generic "javascript proxy" Jupyter notebook widget.
The idea is that for many purposes this widget will make it easy to use javascript
components without having to implement the "javascript view" side of the widget.

For example to create a jqueryui dialog we don't need any javascript support
because jqueryui is already loaded as part of Jupyter and the proxy widget
supplies access to the needed methods from Python:

     from jp_gene_viz import js_proxy
     from IPython.display import display
     js_proxy.load_javascript_support()
     dialog = js_proxy.ProxyWidget()
     command = dialog.element().html("Hello from jqueryui").dialog()
     display(dialog)
     dialog.send_command(command)

The strategy is to pass a sequence of encoded javascript "commands" as a JSON
object to the generic widget proxy and have the proxy execute javascript actions
in response to the commands.  Commands can be chained using "chaining".

(object.method1(...).
    method2(...).
    method3(...)
    )

Results for the last command of the chain are passed back to the
Python widget controller object (to a restricted recursive depth)
except that non-JSON permitted values are mapped to None.

Here are notes on the encoding function E for the JSON commands and their interpretation
as javascript actions:

WIDGET INTERFACE: widget.element()
JSON ENCODING: ["element"]
JAVASCRIPT ACTION: get the this.$el element for the widget.
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
import threading
import types


# In the IPython context get_ipython is a builtin.
# get a reference to the IPython notebook object.
ip = IPython.get_ipython()

JAVASCRIPT_EMBEDDING_TEMPLATE = u"""
(function () {{
    {debugger_string}
    var do_actions = function () {{
        var element = $("#{div_id}");
        // define special functions...
        element.New = function(klass, args) {{
            var obj = Object.create(klass.prototype);
            return klass.apply(obj, args) || obj;
        }};
        element.Fix = function () {{
            // do nothing (not implemented.)
        }}
        var f;  // named function variable for debugging.
        {actions};
    }};
    var wait_for_libraries = function () {{
        var names = {names};
        for (var i=0; i<names.length; i++) {{
            var library = undefined;
            try {{
                library = eval(names[i]);
            }} catch (e) {{
                // do nothing
            }}
            if ((typeof library) == "undefined") {{
                return window.setTimeout(wait_for_libraries, 500);
            }}
        }}
        return do_actions();
    }};
    wait_for_libraries();
}})();
"""

HTML_EMBEDDING_TEMPLATE = (u"""
<div id="{div_id}"></div>
<script>""" +
JAVASCRIPT_EMBEDDING_TEMPLATE + """
</script>
""")

# For creating unique DOM identities for embedded objects
IDENTITY_COUNTER = [int(time.time()) % 10000000]

@widgets.register
class JSProxyWidget(widgets.DOMWidget):
    """Introspective javascript proxy widget."""
    _view_name = Unicode('JSProxyView').tag(sync=True)
    _model_name = Unicode('JSProxyModel').tag(sync=True)
    _view_module = Unicode('jp_proxy_widget').tag(sync=True)
    _model_module = Unicode('jp_proxy_widget').tag(sync=True)
    _view_module_version = Unicode('^0.1.0').tag(sync=True)
    _model_module_version = Unicode('^0.1.0').tag(sync=True)

    # traitlet port to use for sending commends to javascript
    #commands = traitlets.List([], sync=True)

    # Rendered flag sent by JS view after render is complete.
    rendered = traitlets.Bool(False, sync=True)

    # traitlet port to receive results of commands from javascript
    results = traitlets.List([], sync=True)

    # traitlet port to receive results of callbacks from javascript
    callback_results = traitlets.List([], sync=True)

    verbose = False

    def __init__(self, *pargs, **kwargs):
        super(JSProxyWidget, self).__init__(*pargs, **kwargs)
        self.counter = 0
        self.count_to_results_callback = {}
        self.default_event_callback = None
        self.identifier_to_callback = {}
        #self.callback_to_identifier = {}
        self.on_trait_change(self.handle_callback_results, "callback_results")
        self.on_trait_change(self.handle_results, "results")
        self.on_trait_change(self.handle_rendered, "rendered")
        #print "registered on_msg(handle_custom_message)"
        self.on_msg(self.handle_custom_message)
        self.buffered_commands = []
        self.commands_awaiting_render = []
        self.last_commands_sent = []

    def handle_rendered(self, att_name, old, new):
        "when rendered send any commands awaiting the render event."
        if self.commands_awaiting_render:
            self.send_commands([])

    def send_custom_message(self, indicator, payload):
        package = { 
            "indicator": indicator,
            "payload": payload,
        }
        self.send(package)

    def handle_custom_message(self, widget, data, *etcetera):
        self._last_message_data = data

    def embedded_html(self, debugger=False, await=[], template=HTML_EMBEDDING_TEMPLATE, div_id=None):
        """
        Translate buffered commands to static HTML.
        """
        assert type(await) is list
        await_string = json.dumps(await)
        IDENTITY_COUNTER[0] += 1
        if div_id is None:
            div_id = "jupyter_proxy_widget" + str(IDENTITY_COUNTER[0])
        #print("id", div_id)
        debugger_string = "// Initialize static widget display with no debugging."
        if debugger:
            debugger_string = "// Debug mode for static widget display\ndebugger;"
        commands = self.buffered_commands
        js_commands = [to_javascript(c) for c in commands]
        command_string = indent_string(";\n".join(js_commands), 2)
        #return HTML_EMBEDDING_TEMPLATE % (div_id, debugger_string, div_id, command_string)
        return template.format(
            div_id=div_id,
            debugger_string=debugger_string,
            actions=command_string,
            names=await_string)

    def embed(self, debugger=False, await=[]):
        """
        Embed the buffered commands into the current notebook as static HTML.
        """
        embedded_html = self.embedded_html(debugger, await=await)
        display(HTML(embedded_html))

    def embedded_javascript(self, debugger=False, await=[], div_id=None):
        return self.embedded_html(debugger, await, template=JAVASCRIPT_EMBEDDING_TEMPLATE, div_id=div_id)

    def save_javascript(self, filename, debugger=False, await=[], div_id=None):
        out = open(filename, "w")
        js = self.embedded_javascript(debugger, await, div_id=div_id)
        out.write(js)

    def __call__(self, command):
        "Add a command to the buffered commands. Convenience."
        self.buffered_commands.append(command)
        return command

    def flush(self, results_callback=None, level=1):
        "send the buffered commands and clear the buffer. Convenience."
        commands = self.buffered_commands
        self.buffered_commands = []
        return self.send_commands(commands, results_callback, level)

    def save(self, name, reference):
        """
        Proxy to save referent in the element namespace by name.
        The command to save the element is buffered and the return
        value is a reference to the element by name.
        This must be followed by a flush() to execute the command.
        """
        elt = self.element()
        save_command = elt._set(name, reference)
        # buffer the save operation
        self(save_command)
        # return the referency bu name
        return getattr(elt, name)

    def save_new(self, name, constructor, arguments):
        """
        Construct a 'new constructor(arguments)' and save in the element namespace.
        Store the construction in the command buffer and return a reference to the
        new object.
        This must be followed by a flush() to execute the command.
        """
        new_reference = self.element().New(constructor, arguments)
        return self.save(name, new_reference)

    def save_function(self, name, arguments, body):
        """
        Buffer a command to create a JS function using "new Function(...)"
        """
        klass = self.window().Function
        return self.save_new(name, klass, list(arguments) + [body])

    def function(self, arguments, body):
        klass = self.window().Function
        return self.element().New(klass, list(arguments) + [body])

    def handle_results(self, att_name, old, new):
        "Callback for when results arrive after the JS View executes commands."
        if self.verbose:
            print ("got results", new)
        [identifier, json_value] = new
        i2c = self.identifier_to_callback
        results_callback = i2c.get(identifier)
        if results_callback is not None:
            del i2c[identifier]
            results_callback(json_value)

    def handle_callback_results(self, att_name, old, new):
        "Callback for when the JS View sends an event notification."
        if self.verbose:
            print ("got callback results", new)
        [identifier, json_value, arguments, counter] = new
        i2c = self.identifier_to_callback
        results_callback = i2c.get(identifier)
        if results_callback is not None:
            results_callback(json_value, arguments)

    def send_command(self, command, results_callback=None, level=1):
        "Send a single command to the JS View."
        return self.send_commands([command], results_callback, level)

    def send_commands(self, commands_iter, results_callback=None, level=1):
        "Send several commands fo the JS View."
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
            self.send_custom_message("commands", payload)
            self.last_commands_sent = payload
            return payload
        else:
            # wait for render event before sending commands.
            print "waiting for render!", commands
            self.commands_awaiting_render.extend(commands)
            return ("awaiting render", commands)
    
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

    def callback(self, callback_function, data, level=1, delay=False):
        "Create a 'proxy callback' to receive events detected by the JS View."
        assert level > 0, "level must be positive " + repr(level)
        assert level <= 5, "level cannot exceed 5 " + repr(level)
        count = self.counter
        self.counter = count + 1
        command = CallMaker("callback", count, data, level)
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
            arguments = [self.element()]
        return self.send_command(self.function(["element"], "debugger;")(self.element()))

    def element(self):
        "Return a proxy reference to the Widget JQuery element this.$el."
        return CommandMaker("element")

    def window(self):
        "Return a proxy reference to the browser window top level name space."
        return CommandMaker("window")


def validate_commands(commands, top=True):
    """
    Validate a command sequence (and convert to list formate if needed.)
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
        elif indicator == "id":
            assert len(remainder) == 1, "id takes one argument only " + repr(remainder)
        elif indicator == "list":
            remainder = validate_commands(remainder, top=False)
        elif indicator == "dict":
            [d] = remainder
            d = dict((k, validate_command(d[k], top=False)) for k in d)
            remainder = [d]
        elif indicator == "callback":
            [numerical_identifier, untranslated_data, level] = remainder
            assert type(numerical_identifier) is int, \
                "must be integer " + repr(numerical_identifier)
            assert type(level) is int, \
                "must be integer " + repr(level)
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
        elif json_value is None:
            json_value = json.dumps(thing, indent=indent)
        return indent_string(json_value, level)



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

    indicators = {dict: "dict", list: "list"}

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


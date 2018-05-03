var widgets = require('@jupyter-widgets/base');
var _ = require('lodash');


// Custom Model. Custom widgets models must at least provide default values
// for model attributes, including
//
//  - `_view_name`
//  - `_view_module`
//  - `_view_module_version`
//
//  - `_model_name`
//  - `_model_module`
//  - `_model_module_version`
//
//  when different from the base class.

// When serialiazing the entire widget state for embedding, only values that
// differ from the defaults will be specified.
var JSProxyModel = widgets.DOMWidgetModel.extend({
    defaults: _.extend(widgets.DOMWidgetModel.prototype.defaults(), {
        _model_name : 'JSProxyModel',
        _view_name : 'JSProxyView',
        _model_module : 'jp_proxy_widget',
        _view_module : 'jp_proxy_widget',
        _model_module_version : '0.1.0',
        _view_module_version : '0.1.0'
    })
});

// Define a require.js module to help with loading external modules
// from source code
var module_name_to_text = {};

//var loader_defined = false;
var JSProxyLoad = "JSProxyLoad";

// Alias the require.js define and require functions.  xxxx is there a better way?
var requirejs = window["require"];
var definejs = window["define"];

// Define the loader at the last minute...
var define_loader = function() {
    if (!requirejs.defined(JSProxyLoad)) {
        module_name_to_text = [];
        definejs(JSProxyLoad, [], function() {
            return {
                normalize: function(name, _) {
                    return name; // is this needed?
                },
                load: function (name, req, onload, config) {
                    var text = module_name_to_text[name];
                    onload.fromText(text);
                    // delete the text? xxxx
                }
            };
        });
        // self test.
        var dummy_text = 'define([], function() { console.log("loading dummy..."); return " dummy value!! "; })';
        module_name_to_text["xxxdummy"] = dummy_text;
        requirejs([JSProxyLoad + "!xxxdummy"], function(the_value) {
            console.log("JSProxyLoad for xxx_dummy succeeded. " + the_value);
        });
    }
    //loader_defined = true;
}

// Custom View. Renders the widget model.
var JSProxyView = widgets.DOMWidgetView.extend({

    render: function() {
        debugger;
        var that = this;
        that._json_accumulator = [];
        that.on("displayed", function() {
            that.update();
        });

        that.model.on("msg:custom", function(content, buffers, widget) {
            that.handle_custom_message(content, buffers, widget);
        })
        // Wrap $el as a proper jQuery object
        that.$$el = $(that.$el);

        // _load_js_module function
        // Load a require.js module and store the loaded object as $$el[name].
        // note that there is a hypothetical delay before the module becomes available.
        that.$$el._load_js_module = function(name, text) {
            define_loader();
            // store the text in global dictionary for use by the plugin
            module_name_to_text[name] = text;
            // use the require.js plugin above to load the module, then store it in $$el when done.
            requirejs([JSProxyLoad + "!" + name], function(the_module) {
                that.$$el[name] = the_module;
            });
        };

        // "new" keyword emulation
        // http://stackoverflow.com/questions/17342497/dynamically-control-arguments-while-creating-objects-in-javascript
        that.$$el.New = function(klass, args) {
            var obj = Object.create(klass.prototype);
            return klass.apply(obj, args) || obj;
        };

        // fix key bindings for wayward element.
        // XXXX This is a bit of a hack that may not be needed in future
        // Jupyter releases.
        that.$$el.Fix = function(element) {
            debugger;
            that.model.widget_manager.keyboard_manager.register_events(element);
        };

        that.model.set("rendered", true);
        that.touch();
    },

    // String constants for messaging
    INDICATOR: "indicator",
    PAYLOAD: "payload",
    RESULTS: "results",
    CALLBACK_RESULTS: "callback_results",
    JSON_CB_FRAGMENT: "jcb_results",
    JSON_CB_FINAL: "jcb_final",
    COMMANDS: "commands",
    COMMANDS_FRAGMENT: "cm_fragment",
    COMMANDS_FINAL: "cm_final",

    update: function(options) {
        // do nothing.
        //var that = this;
        //var commands = that.model.get("commands");
        //return that.execute_commands(commands);
    },

    execute_commands: function(commands) {
        var that = this;
        var results = [];
        if (commands && commands.length >= 2) {
            var command_counter = commands[0];
            var command_list = commands[1];
            var level = commands[2];
            level = that.check_level(level);
            try {
                _.each(command_list, function(command,i) {
                    var result = that.execute_command(command);
                    results[i] = that.json_safe(result, level);
                });
            } catch (err) {
                results.push("" + err);
            }
            //that.model.set("commands", []);
            //that.model.set("results", [command_counter, results])
            //that.touch();
        } else {
            results.push("no commands sent?");
        }
        that.send_custom_message(that.RESULTS, [command_counter, results])
        return results;
    },

    send_custom_message: function(indicator, payload) {
        var that = this;
        message = {};
        message[that.INDICATOR] = indicator;
        message[that.PAYLOAD] = payload;
        that.model.send(message)
    },

    handle_custom_message: function(content, buffers, widget) {
        var that = this;
        var indicator = content[that.INDICATOR];
        var payload = content[that.PAYLOAD];
        if (indicator == that.COMMANDS) {
            that._json_accumulator = [];
            that.execute_commands(payload);
        } else if (indicator == that.COMMANDS_FRAGMENT) {
            that._json_accumulator.push(payload);
        } else if (indicator == that.COMMANDS_FINAL) {
            var acc = that._json_accumulator;
            that._json_accumulator = [];
            acc.push(payload);
            var json_str = acc.join("");
            var commands = JSON.parse(json_str);
            that.execute_commands(commands);
        } else {
            console.log("invalid custom message indicator " + indicator);
        }
    },

    execute_command: function(command) {
        var that = this;
        var result = command;
        if ($.isArray(command)) {
            var indicator = command[0];
            var remainder = command.slice();
            remainder.shift();
            if (indicator == "element") {
                // Make sure the element is wrapped as a proper JQuery(UI) object
                if (!that.$$el) {
                    that.$$el = $(that.$el);
                }
                result = that.$$el;
            } else if (indicator == "window") {
                result = window;
            } else if (indicator == "method") {
                var target_desc = remainder.shift();
                var target = that.execute_command(target_desc);
                var name = remainder.shift();
                var args = remainder.map(that.execute_command, that);
                var method = target[name];
                if (method) {
                    result = method.apply(target, args);
                } else {
                    result = "In " + target + " no such method " + name;
                }
            } else if (indicator == "function") {
                var function_desc = remainder.shift();
                var function_value = that.execute_command(function_desc);
                var args = remainder.map(that.execute_command, that);
                // Use "that" as the "this" value for function values?
                result = function_value.apply(that, args);
            } else if (indicator == "id") {
                result = remainder[0];
            } else if (indicator == "list") {
                result = remainder.map(that.execute_command, that);
            } else if (indicator == "dict") {
                result = {}
                var desc = remainder[0];
                for (var key in desc) {
                    var key_desc = desc[key];
                    var val = that.execute_command(key_desc);
                    result[key] = val;
                }
            } else if (indicator == "callback") {
                var identifier = remainder.shift();
                var data = remainder.shift();
                var level = remainder.shift();
                var segmented = remainder.shift();
                // sanity check
                level = that.check_level(level);
                result = that.callback_factory(identifier, data, level, segmented);
            } else if (indicator == "get") {
                var target_desc = remainder.shift();
                var target = that.execute_command(target_desc);
                var name = remainder.shift();
                try {
                    result = target[name];
                } catch(err) {
                    result = "failed to get "+name+" from "+target+" :: "+err;
                }
            } else if (indicator == "set") {
                var target_desc = remainder.shift();
                var target = that.execute_command(target_desc);
                var name = remainder.shift();
                var value_desc = remainder.shift()
                var value = that.execute_command(value_desc);
                target[name] = value;
                result = target;
            } else if (indicator == "null") {
                target_desc = remainder.shift();
                that.execute_command(target_desc);
                result = null;
            } else if (indicator == "bytes") {
                var hexstr = remainder[0];
                result = this.from_hex(hexstr);
            } else {
                result = "Unknown indicator " + indicator;
            }
        }
        return result;
    },

    check_level: function(level) {
        if ((typeof level) != "number" || (level < 0)) {
            level = 0;
        } else if (level > 5) {
            level = 5;
        }
        return level;
    },

    callback_factory: function(identifier, data, level, segmented) {
        // create a callback which sends a message back to the Jupyter Kernel
        var that = this;
        // Counter makes sure change is noticed even if other arguments don't change.
        var counter = 0;
        var handler = function () {
            counter += 1;
            var payload = that.json_safe([identifier, data, arguments, counter], level + 1);
            //that.model.set("callback_results", payload);
            //that.touch();
            if ((segmented) && (segmented > 0)) {
                that.send_segmented_message(that.JSON_CB_FRAGMENT, that.JSON_CB_FINAL, payload, segmented);
            } else {
                that.send_custom_message("callback_results", payload);
            }
        };
        return handler;
    },

    send_segmented_message(frag_indicator, final_indicator, payload, segmented) {
        var that = this;
        var json_str = JSON.stringify(payload);
        var json_len = json_str.length;
        var cursor = 0;
        while ((cursor + segmented) < json_len) {
            var next_cursor = cursor + segmented;
            var fragment = json_str.substring(cursor, next_cursor);
            cursor = next_cursor;
            that.send_custom_message(frag_indicator, fragment);
        }
        var tail = json_str.substring(cursor, json_len);
        that.send_custom_message(final_indicator, tail);
    },

    to_hex: function(int8) {
        var length = int8.length;
        var hex_array = Array(length);
        for (var i=0; i<length; i++) {
            var b = int8[i];
            var h = b.toString(16);
            if (h.length==1) {
                h = "0" + h
            }
            hex_array[i] = h;
        }
        return hex_array.join("");
    },

    from_hex: function(hexstr) {
        var length2 = hexstr.length;
        if ((length2 % 2) != 0) {
            throw "hex string length must be multiple of length 2";
        }
        var length = length2 / 2;
        var result = new Uint8Array(length);
        for (var i=0; i<length; i++) {
            var i2 = 2 * i;
            var h = hexstr.substring(i2, i2+2);
            var b = parseInt(h, 16);
            result[i] = b;
        }
        return result;
    },

    json_safe: function(val, depth) {
        // maybe expand later as need arises
        var that = this;
        var ty = (typeof val);
        if ((ty == "number") || (ty == "string") || (ty == "boolean")) {
            return val;
        }
        if ((val instanceof Uint8Array) || (val instanceof Uint8ClampedArray)) {
            // send as hexidecimal string
            return that.to_hex(val);
        }
        if (!val) {
            // translate all other falsies to None
            return null;
        }
        if (((typeof depth) == "number") && (depth > 0)) {
            if ($.isArray(val)) {
                var result = [];
                _.each(val, function(elt, i) {
                    var r = that.json_safe(elt, depth-1);
                    if (r != null) {
                        result[i] = r;
                    }
                });
                return result;
            } else {
                var result = {};
                for (var key in val) {
                    var jv = that.json_safe(val[key], depth-1);
                    if (jv != null) {
                        result[key] = jv;
                    }
                }
                return result;
            }
        }
        return null;
    }

    //value_changed: function() {
        //this.el.textContent = this.model.get('value');
    //}
});


module.exports = {
    JSProxyModel : JSProxyModel,
    JSProxyView : JSProxyView
};

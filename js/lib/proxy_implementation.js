var widgets = require('@jupyter-widgets/base');
var _ = require('lodash');

// locally packaged jquery -- use only if needed!
var jquery_ = require('jquery');


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
        _model_module_version : '0.3.4',
        _view_module_version : '0.3.4ß'
    })
});

//var loader_defined = false;
var JSProxyLoad = "JSProxyLoad";

// Custom View. Renders the widget model.
var JSProxyView = widgets.DOMWidgetView.extend({

    render: function() {

        var that = this;
        this.el.textContent = "Uninitialized Proxy Widget";

        that._json_accumulator = [];

        that.on("displayed", function() {
            that.update();
        });

        that.model.on("msg:custom", function(content, buffers, widget) {
            that.handle_custom_message(content, buffers, widget);
        })

        // Wrap $el as a proper jQuery object
        // This is the "element" exposed on the Python side.
        if (window["jQuery"]) {
            // use the window jQuery if available
            jquery_ = window["jQuery"];
        } else {
            // put jQuery into the environment xxx maybe make this optional?
            window["jQuery"] = jquery_;
            window["$"] = jquery_;
        }
        that.$$el = jquery_(that.el);
        that.$$el.jQuery = jquery_;
        that.$$el._ = _;

        // trigger callbacks if vanilla javascript modules have/have not been loaded.
        // no-op callbacks can be falsy.
        that.$$el.test_js_loaded = function(names, is_loaded_callback, not_loaded_callback, silent) {
            var all_loaded = true;
            for (var i=0; i<names.length; i++) {
                var name = names[i];
                var name_is_loaded = false;
                var status = that.loaded_js_by_name[name];
                if (status) {
                    complete = status[0];
                    if (complete) {
                        if (is_loaded_callback) {
                            is_loaded_callback();
                        }
                        name_is_loaded =true;
                    }
                }
                if (!name_is_loaded) {
                    all_loaded = false;
                }
            }
            if (all_loaded) {
                if (is_loaded_callback) {
                    is_loaded_callback();
                }
            } else {
                if (not_loaded_callback) {
                    not_loaded_callback();
                } else if (!silent) {
                    that.set_error_msg("test_js_loaded failed " + names);
                }
            }
            return all_loaded;
        };

        // execute action when vanilla javascript modules have been loaded
        //  xxxx this duplicates logic in load_js_command below?
        that.$$el.when_loaded = function(names, action, failure, delay, limit) {
            if (!delay) {
                delay = 10;
            }
            if (!limit) {
                limit = 1000;
            }
            var counter = 0;
            var attempt_action = function () {
                counter += delay;
                // test for load silently.
                if (that.$$el.test_js_loaded(names, null, null, true)) {
                    return action();
                }
                // otherwise try again later, maybe
                if (counter < limit) {
                    return setTimeout(attempt_action, delay);
                } else {
                    if (failure) {
                        return failure();
                    } else {
                        that.set_error_msg("when loaded timed out waiting for " + names);
                    }
                }
            }
            attempt_action();
        };

        that.$el.set_error_msg = function(msg) {
            that.set_error_msg(msg);
        };

        // Store aliases to the require and define functions (if available).
        // Call the failure callback if the functions cannot be found.
        that.$$el.alias_require = function (success_callback, failure_callback) {
            var window_require = window["require"];
            if (window_require) {
                that.$$el.requirejs = window["require"];
                that.$$el.definejs = window["define"];
                console.log("alias require succeeded.");
                if (success_callback) {
                    success_callback();
                }
            } else if (failure_callback) {
                console.log("alias require failed");
                failure_callback();
            }
        };

        // _load_js_module function
        // Load a require.js module and store the loaded object as $$el[name].
        // note that there is a hypothetical delay before the module becomes available.
        that.$$el._load_js_module = function(name, text) {
            console.log("load js module " + name);
            // require js must be loaded previously somehow
            that.$$el.alias_require()
            if (that.$$el.requirejs) {
                var definejs = that.$$el.definejs;
                var redefiner = function(name) {
                    var define_replacement = function (a, b, c) {
                        var defined_name = name;
                        var requirements;
                        var defining_function;
                        if ((typeof a) == "string") {
                            // console.log("renamed define "+a+" : "+name);
                            defined_name = a;
                            requirements = b;
                            defining_function = c;
                        } else {
                            // console.log("de-anonymized define: " + name);
                            requirements = a;
                            defining_function = b;
                        }
                        console.log("defining " + defined_name);
                        definejs(defined_name, requirements, defining_function);
                        if (defined_name != name) {
                            console.log("  ...and also defining " + name);
                            definejs(name, requirements, defining_function);
                        }
                    };
                    if ((((typeof definejs) !== "undefined") && (definejs !== null)) && (definejs.amd !== null)) {
                        define_replacement.amd = definejs.amd;
                    }
                    return define_replacement;
                };
                // evaluate the text in an anonymous function with "define" rebound using redefiner(name)
                var js_text_fn = Function("define", text);
                js_text_fn(redefiner(name));
            } else {
                var msg = "Cannot load_js_module if requirejs is not available: " + name;
                that.set_error_msg(msg);
                return msg;
            }
        };

        // "new" keyword emulation
        // http://stackoverflow.com/questions/17342497/dynamically-control-arguments-while-creating-objects-in-javascript
        that.$$el.New = function(klass, args) {
            try {
                var obj = Object.create(klass.prototype);
                return klass.apply(obj, args) || obj;
            } catch (err) {
                var msg = "Error in element.New " + err;
                that.set_error_msg(msg);
                throw new Error(msg);
            }
        };

        // fix key bindings for wayward element.
        // XXXX This is a bit of a hack that may not be needed in future
        // Jupyter releases.
        //that.$$el.Fix = function(element) {
        //    that.model.widget_manager.keyboard_manager.register_events(element);
        //};

        that.$$el.no_overflow = function() {
            // prevent overflow scrollbars on the widget (and parents)
            var div = that.$$el[0];
            for (var count=0; count<10; count++) {
                if (div.style) {
                    div.style.overflowX = "visible";
                    div.style.overflow = "visible";
                    div.style.height = "auto";
                }
                div = div.parentNode;
                if (!div) {
                    break;
                }
            }
        };

        // Just do it -- we never want scrollbars on widgets.
        that.$$el.no_overflow();

        that.model.set("rendered", true);
        that.touch();
    },

    set_error_msg: function(message) {
        var that = this;
        that.error_msg = message;
        that.model.set("error_msg", message);
        that.touch();
        console.error("proxy widget: " + message)
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
        // cl("execute_commands " + commands.length);
        var that = this;
        var results = [];
        if (commands && commands.length >= 2) {
            var command_counter = commands[0];
            // cl("command_counter=" + command_counter)
            var command_list = commands[1];
            var level = commands[2];
            level = that.check_level(level);
            // resume command execution at the beginning...
            return that.resume_execute_commands(results, command_list, command_counter, level, 0);
            /*
            try {
                _.each(command_list, function(command,i) {
                    var result = that.execute_command(command);
                    results[i] = that.json_safe(result, level);
                });
            } catch (err) {
                var msg = "" + err;
                results.push(msg);
                that.set_error_msg(msg);
            }
            */
        } else {
            results.push("no commands sent?");
        }
        that.send_custom_message(that.RESULTS, [command_counter, results])
        return results;
    },

    resume_execute_commands: function(results, command_list, command_counter, level, index) {
        // resume command execution starting at index
        var that = this;
        var evaluator = null;
        var evaluation_index = index;
        var command = null;
        try {
            for (var i=index; i<command_list.length; i++) {
                evaluation_index = i;
                command = command_list[i];
                var evaluation = that.execute_command(command);
                evaluator = evaluation.evaluator;
                var result = evaluation.result;
                if (evaluator) {
                    // must evaluate result async and resume later
                    break;
                } else {
                    // store result now and proceed
                    results[i] = that.json_safe(result, level);
                }
            }
            if (evaluator) {
                // The evaluation loop has been stopped by an async operation.
                // evaluate at evaluation_index async and resume later
                var resolver = function(value_for_command) {
                    // store the calculated result
                    results[evaluation_index] = value_for_command;
                    // continue evaluating any remaining commands, starting at the next command
                    return that.resume_execute_commands(results, command_list, command_counter, level,
                        evaluation_index+1)
                };
                // call the async evaluator
                evaluator(resolver);
            } else {
                // evaluation complete: send results
                // cl(command_counter + " execute commands done " + results.length);
                that.send_custom_message(that.RESULTS, [command_counter, results])
                return results
            }
        } catch (err) {
            var msg = "" + err;
            results.push(msg);
            that.set_error_msg(msg);
        }
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
            var msg = "invalid custom message indicator " + indicator;
            that.set_error_msg(msg);
        }
    },

    execute_command_result: function(command) {
        // execute the command and ignore the evaluator if provided
        return this.execute_command(command).result;
    },

    execute_command: function(command) {
        var that = this;
        var result = command;
        // evaluator, if set is a function evaluator(resolver)
        //   which promises to eventually call resolver(value_for_command)
        //   perhaps after a few event loop iterations...
        // evaluator is ignored except at the top level evaluation loop
        //   where it takes precedence over the result.
        var evaluator = null;
        if (jquery_.isArray(command)) {
            var indicator = command[0];
            var remainder = command.slice();
            remainder.shift();
            if (indicator == "element") {
                // Make sure the element is wrapped as a proper JQuery(UI) object
                //if (!that.$$el) {
                //    that.$$el = $(that.$el);
                //}
                result = that.$$el;
            } else if (indicator == "window") {
                result = window;
            } else if (indicator == "method") {
                var target_desc = remainder.shift();
                var target = that.execute_command_result(target_desc);
                var name = remainder.shift();
                var args = remainder.map(that.execute_command_result, that);
                // cl("method call " + target + "." + name);
                var method = target[name];
                if (method) {
                    result = method.apply(target, args);
                } else {
                    result = "In " + target + " no such method " + name;
                    that.set_error_msg(result);
                }
            } else if (indicator == "function") {
                var function_desc = remainder.shift();
                var function_value = that.execute_command_result(function_desc);
                var args = remainder.map(that.execute_command_result, that);
                // Use "that" as the "this" value for function values?
                result = function_value.apply(that, args);
            } else if (indicator == "id") {
                result = remainder[0];
            } else if (indicator == "list") {
                result = remainder.map(that.execute_command_result, that);
            } else if (indicator == "dict") {
                result = {}
                var desc = remainder[0];
                for (var key in desc) {
                    var key_desc = desc[key];
                    var val = that.execute_command_result(key_desc);
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
                var target = that.execute_command_result(target_desc);
                var name = remainder.shift();
                try {
                    result = target[name];
                } catch(err) {
                    result = "failed to get "+name+" from "+target+" :: "+err;
                    that.set_error_msg(result);
                }
            } else if (indicator == "set") {
                var target_desc = remainder.shift();
                var target = that.execute_command_result(target_desc);
                var name = remainder.shift();
                var value_desc = remainder.shift()
                var value = that.execute_command_result(value_desc);
                target[name] = value;
                result = target;
            } else if (indicator == "null") {
                target_desc = remainder.shift();
                that.execute_command_result(target_desc);
                result = null;
            } else if (indicator == "load_css") {
                result = "load_css_async";
                css_name = remainder.shift();
                css_text = remainder.shift();
                evaluator = that.load_css_async(css_name, css_text);
            } else if (indicator == "load_js") {
                result = "load_javascript_async";
                js_name = remainder.shift();
                js_text = remainder.shift();
                evaluator = that.load_js_async(js_name, js_text);
            } else if (indicator == "bytes") {
                var hexstr = remainder[0];
                result = that.from_hex(hexstr);
            } else {
                var msg = "Unknown command indicator " + indicator;
                result = msg;
                that.set_error_msg(msg);
            }
        }
        //return result;
        return {result: result, evaluator: evaluator};
    },

    load_css_async: function(css_name, css_text) {
        // Return a function evaluator(resolver)
        // which promises to load the css_text and call the
        // resolver() when the load is complete.
        var that = this;
        var evaluator = function(resolver) {
            // if the sheet already exists, just succeed
            if (that.sheet_name_exists(css_name)) {
                return resolver(css_name);
            }
            // otherwise create the style and wait for stylesheet
            that.$$el.jQuery("<style>")
            .prop("type", "text/css")
            //.prop("title", css_name)
            .prop("href", css_name)
            .html("\n"+css_text)
            .appendTo("head");
            // loop a while waiting for the stylesheet to appear.
            var done_test = function() {
                return that.sheet_name_exists(css_name);
            };
            return that.evaluation_test_polling_loop(done_test, css_name, resolver);
        };
        return evaluator;
    },

    evaluation_test_polling_loop: function(eval_test, resolve_value, resolver) {
        var that = this;
        var count = 0;
        var limit = 100;
        var wait_milliseconds = 10;
        var test_poll = function () {
            count += 1;
            if (eval_test()) {
                return resolver(resolve_value)
            }
            // otherwise try again, maybe
            if (count < limit) {
                setTimeout(test_poll, wait_milliseconds);
            } else {
                var message = "timeout awaiting " + resolve_value;
                that.set_error_msg(message);
                return resolver(message);
            }
        };
        test_poll();
    },

    sheet_name_exists: function(css_name) {
        // test if a css sheet name is known
        var sheets = document.styleSheets;
        for (var i=0; i<sheets.length; i++) {
            var sheet = sheets[i];
            if ((sheet.ownerNode) && (sheet.ownerNode.href == css_name)) { // (sheet.title == css_name) {
                return sheet;
            }
        }
        return false;
    },

    // cache of name to [completion status, text] for loaded javascript
    loaded_js_by_name: {},

    load_js_async: function(js_name, js_text) {
        // Return a function evaluator(resolver)
        // which promises to load the css_text and call the
        // resolver() when the load is complete.
        console.log("load_js_async " + js_name);
        var that = this;
        var evaluator = function(resolver) {
            // we are done when the loaded javascript matches and is marked complete.
            var done_test = function() {
                var load_entry = that.loaded_js_by_name[js_name];
                if (load_entry) {
                    var status = load_entry[0];
                    var loaded_text = load_entry[1];
                    if ((status) && (loaded_text == js_text)) {
                        return true;
                    }
                };
                return false;
            };
            // if the text is already loading, wait for completion
            var load_entry = that.loaded_js_by_name[js_name];
            if ((load_entry) && (load_entry[1] == js_text)) {
                return that.evaluation_test_polling_loop(done_test, js_name, resolver);
            };
            // otherwise install the javascript...
            //var all_done = function() {
            //    // when done mark the text as loaded
            //    that.loaded_js_by_name[js_name] = [true, js_text];
            //};
            // before done, mark the text as loading but not complete
            that.loaded_js_by_name[js_name] = [false, js_text];
            // compile the text NOT wrapped in an anonymous function
            var function_body = [
                // "(function() {",
                'console.log("eval-loading ' + js_name + '");',
                // undefine the define function temporarily, just in case!
                'if (typeof define != "undefined") { jQuery.save_global_define = define; }',
                'try {',
                '    if (typeof define != "undefined") { define = undefined; }',
                js_text,
                '    ;console.log("finished eval-loading ' + js_name + '");',
                '} finally { ',
                '    if ((jQuery.save_global_define) && (typeof define == "undefined") ) {',
                '        define = jQuery.save_global_define; ',
                '    } }',
                //"})();",
                //"all_done();"
            ].join("\n");
            //var js_text_fn = Function("all_done", function_body);
            // execute the code and completion call
            //js_text_fn(all_done);
            // Evaluate in global context!
            eval.call(window, function_body);
            // mark as complete.
            that.loaded_js_by_name[js_name] = [true, js_text];
            // cl("resolving load for " + js_name);
            // resolve
            return resolver(js_name);
        };
        // cl("returning load evaluator load_js_async " + js_name);
        return evaluator;
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
            if (jquery_.isArray(val)) {
                var result = [];
                _.each(val, function(elt, i) {
                    var r = that.json_safe(elt, depth-1);
                    //if (r != null) {
                    result[i] = r;
                    //}
                });
                return result;
            } else {
                var result = {};
                for (var key in val) {
                    var jv = that.json_safe(val[key], depth-1);
                    //if (jv != null) {
                    result[key] = jv;
                    //}
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

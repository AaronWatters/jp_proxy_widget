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


// Custom View. Renders the widget model.
var JSProxyView = widgets.DOMWidgetView.extend({

    render: function() {
        debugger;
        var that = this;
        that.on("displayed", function() {
            that.update();
        });

        that.model.on("msg:custom", function(content, buffers, widget) {
            that.handle_custom_message(content, buffers, widget);
        })
        // Wrap $el as a proper jQuery object
        that.$$el = $(that.$el);
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

    update: function(options) {
        var that = this;
        var commands = that.model.get("commands");
        return that.execute_commands(commands);
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
            that.model.set("commands", []);
            that.model.set("results", [command_counter, results])
            that.touch();
        } else {
            results.push("no commands sent?");
        }
        return results;
    },

    handle_custom_message: function(content, buffers, widget) {
        var that = this;
        debugger;
        var indicator = content["indicator"];
        var payload = content["payload"];
        if (indicator == "commands") {
            that.execute_commands(payload);
        }
        // send it back again
        //that.model.send(args);
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
                // sanity check
                level = that.check_level(level);
                result = that.callback_factory(identifier, data, level);
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

    callback_factory: function(identifier, data, level) {
        var that = this;
        // Counter makes sure change is noticed even if other arguments don't change.
        var counter = 0;
        var handler = function () {
            counter += 1;
            var payload = that.json_safe([identifier, data, arguments, counter], level + 1);
            that.model.set("callback_results", payload);
            that.touch();
        };
        return handler;
    },

    json_safe: function(val, depth) {
        // maybe expand later as need arises
        var that = this;
        var ty = (typeof val);
        if ((ty == "number") || (ty == "string") || (ty == "boolean")) {
            return val;
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

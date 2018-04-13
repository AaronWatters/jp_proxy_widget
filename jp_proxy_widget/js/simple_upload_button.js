
/*
jQuery plugin for a simple upload button that
sends file information and contents to a callback

elt.append(elt.simple_upload_button(callback))

Structure follows: https://learn.jquery.com/plugins/basic-plugin-creation/
Logic from http://www.html5rocks.com/en/tutorials/file/dndfiles/
*/

(function($) {
    $.fn.simple_upload_button = function (callback, options) {
        //debugger;
        var settings = $.extend({
            "size_limit": 10000000,
            "style": {"display": "inline-block"},
            "hexidecimal": true,
        }, options);
        var result = $('<input type="file"/>');
        var hex_byte = function (b) {
            var result = b.toString(16);
            if (result.length < 2) {
                result = "0" + result
            }
            return result;
        };
        var to_hex_string = function (buffer) {
            //debugger;
            var bytes = new Uint8Array(buffer);
            return Array.from(bytes).map(hex_byte).join("");
        };
        if (settings.style) {
            result.css(settings.style);
        }
        result.on("change", function(event) {
            var file = this.files[0];
            if (file) {
                var data = {
                    "name": file.name,
                    "type": file.type,
                    "content": null,
                    "size": file.size
                };
                if ((!settings.size_limit) || (settings.size_limit > data.size)) {
                    var reader = new FileReader();
                    reader.onload = function (event) {
                        var result = event.target.result;
                        if (settings.hexidecimal) {
                            data["hexcontent"] = to_hex_string(result);
                        } else {
                            data["content"] = result;
                        }
                        // callback with content (not too big)
                        callback(data);
                    };
                    if (settings.hexidecimal) {
                        reader.readAsArrayBuffer(file);
                    } else {
                        reader.readAsText(file);
                    }
                } else {
                    // invoke callback with no content (too big).
                    callback(data);
                }
            }
        });
        return result;
    };

    $.fn.simple_upload_button.example = function(element) {
        var output_area = $("<pre/>");
        element.append(output_area);
        var callback_function = function(data) {
            output_area.html([
                "name " + data.name,
                "type " + data.type,
                "size " + data.size,
                "===",
                "" + data.content
                ].join("\n"));
        };
        var options = {"hexidecimal": false}
        var upload_button = element.simple_upload_button(callback_function, options);
        element.append(upload_button);
        return element;
    };
})(jQuery);

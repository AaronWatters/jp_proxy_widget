
/*
jQuery plugin for a simple upload button that
sends file information and contents to a callback

elt.append(elt.simple_upload_button(callback))

Structure follows: https://learn.jquery.com/plugins/basic-plugin-creation/
Logic from http://www.html5rocks.com/en/tutorials/file/dndfiles/

The file is delivered to the callback.  

If chunksize is not set the file is delivered all at once

    callback(data)

where data is a mapping and either

    data["hexcontent"]

is the hexidecimal string encoding of the file content 
if options.hexidecimal is true or

    data["content"]

is the untransformed unicode content of the file if
options.hexidecimal is false.

If chunksize is set to a positive integer 
then the content is sent in chunks
in multiple callback(chunkdata) calls where 
nonfinal calls have data["status"] == "more" and the final
call has data["status"] == "done".

If an error occurs the callback will be called with
data["status"] == "error" amd data["message"] will have
more information on the error, such as "file too big."

*/

(function($) {
    $.fn.simple_upload_button = function (callback, options) {
        var settings = $.extend({
            "size_limit": 10000000,  // Don't upload files larger than this.
            "style": {"display": "inline-block"},
            "hexidecimal": true,
            "chunk_size": 0,  // default to all at once
            "continuation_style": false,   // default to 
        }, options);
        var result = $('<input type="file"/>');
        var hex_byte = function (b) {
            var result = b.toString(16);
            if (result.length < 2) {
                result = "0" + result
            }
            return result;
        };
        var size_limit = settings.size_limit;
        var chunk_size = settings.chunk_size;
        var continuation_style = settings.continuation_style;
        var to_hex_string = function (buffer) {
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
                    var blobstart = 0;
                    var blobend = data.size;
                    if ((chunk_size) && (chunk_size>0) && (chunk_size < data.size)) {
                        blobend = chunk_size;
                    }
                    var reader_onload = function (event) {
                        var result = event.target.result;
                        var send_data = Object.assign({}, data);
                        if (settings.hexidecimal) {
                            send_data["hexcontent"] = to_hex_string(result);
                        } else {
                            send_data["content"] = result;
                        }
                        // callback with content (not too big)
                        if (blobend >= data.size) {
                            send_data["status"] = "done";
                            callback(send_data);
                        }
                        else 
                        {
                            send_data["status"] = "more";
                            callback(send_data);
                            blobstart = blobend;
                            blobend += chunk_size;
                            if (blobend > data.size) {
                                blobend = data.size;
                            }
                            set_up_reader();
                        }
                    };
                    var set_up_reader = function () {
                        var reader = new FileReader();
                        reader.onload = reader_onload;
                        var blob = file.slice(blobstart, blobend);
                        if (settings.hexidecimal) {
                            reader.readAsArrayBuffer(blob);
                        } else {
                            reader.readAsText(blob);
                        }
                    };
                    set_up_reader();
                } else {
                    // invoke callback with no content (too big).
                    data["message"] = "file too big.";
                    data["status"] = "error";
                    callback(data);
                }
            }
        });
        return result;
    };

    $.fn.simple_upload_button.example = function(element) {
        var output_area = $("<pre/>");
        element.append(output_area);
        var content_accumulator = "";
        var callback_function = function(data) {
            // accumulate the data until done...
            content_accumulator += data.content;
            if (data.status == "done") {
                output_area.html([
                    "name " + data.name,
                    "type " + data.type,
                    "size " + data.size,
                    "===",
                    "" + content_accumulator
                    ].join("\n"));
                content_accumulator = "";
            }
        };
        // read file one character at a time
        var options = {"hexidecimal": false, "chunk_size": 1,}
        var upload_button = element.simple_upload_button(callback_function, options);
        element.append(upload_button);
        return element;
    };
})(jQuery);

var fenced_code = (function () {

var exports = {};

// Parsing routine that can be dropped in to message parsing
// and formats code blocks
//
// This supports arbitrarily nested code blocks as well as
// auto-completing code blocks missing a trailing close.

// See backend fenced_code.py:71 for associated regexp
var fencestr = "^(~{3,}|`{3,})"            + // Opening Fence
               "[ ]*"                      + // Spaces
               "("                         +
                   "\\{?\\.?"              +
                   "([a-zA-Z0-9_+-./#]*)"  + // Language
                   "\\}?"                  +
               "[ ]*"                      + // Spaces
               ")$";
var fence_re = new RegExp(fencestr);

// Default stashing function does nothing
var stash_func = function (text) {
    return text;
};

var escape_func = function (text) {
    return text;
};

function wrap_code(code) {
    // Trim trailing \n until there's just one left
    // This mirrors how pygments handles code input
    code += '\n';
    while (code.length > 2 && code.substr(code.length - 2) === '\n\n') {
        code = code.substring(0, code.length - 1);
    }
    return '<div class="codehilite"><pre><span></span>' + escape_func(code) + '</pre></div>\n';
}

function wrap_quote(text) {
    var paragraphs = text.split('\n\n');
    var quoted_paragraphs = [];
    // Prefix each quoted paragraph with > at the
    // beginning of each line
    _.each(paragraphs, function (paragraph) {
        var lines = paragraph.split('\n');
        quoted_paragraphs.push(_.map(
                                    _.reject(lines, function (line) { return line === ''; }),
                                    function (line) { return '> ' + line; }).join('\n'));
    });
    return quoted_paragraphs.join('\n\n');
}

function wrap_tex(tex) {
    try {
        return katex.renderToString(tex, {
            displayMode: true,
        });
    } catch (ex) {
        return '<span class="tex-error">' + escape_func(tex) + '</span>';
    }
}

exports.set_stash_func = function (stash_handler) {
    stash_func = stash_handler;
};

exports.set_escape_func = function (escape) {
    escape_func = escape;
};

exports.process_fenced_code = function (content) {
    var input = content.split('\n');
    var output = [];
    var handler_stack = [];
    var consume_line;

    function handler_for_fence(output_lines, fence, lang) {
        // lang is ignored except for 'quote', as we
        // don't do syntax highlighting yet
        return (function () {
            var lines = [];
            if (lang === 'quote') {
                return {
                    handle_line: function (line) {
                        if (line === fence) {
                            this.done();
                        } else {
                            consume_line(lines, line);
                        }
                    },

                    done: function () {
                        var text = wrap_quote(lines.join('\n'));
                        output_lines.push('');
                        output_lines.push(text);
                        output_lines.push('');
                        handler_stack.pop();
                    },
                };
            }

            if (lang === 'math' || lang === 'tex' || lang === 'latex') {
                return {
                    handle_line: function (line) {
                        if (line === fence) {
                            this.done();
                        } else {
                            lines.push(line);
                        }
                    },

                    done: function () {
                        var text = wrap_tex(lines.join('\n'));
                        var placeholder = stash_func(text, true);
                        output_lines.push('');
                        output_lines.push(placeholder);
                        output_lines.push('');
                        handler_stack.pop();
                    },
                };
            }

            return {
                handle_line: function (line) {
                    if (line === fence) {
                        this.done();
                    } else {
                        lines.push(util.rtrim(line));
                    }
                },

                done: function () {
                    var text = wrap_code(lines.join('\n'));
                    // insert safe HTML that is passed through the parsing
                    var placeholder = stash_func(text, true);
                    output_lines.push('');
                    output_lines.push(placeholder);
                    output_lines.push('');
                    handler_stack.pop();
                },
            };
        }());
    }

    function default_hander() {
        return {
            handle_line: function (line) {
                consume_line(output, line);
            },
            done: function () {
                handler_stack.pop();
            },
        };
    }

    consume_line = function consume_line(output_lines, line) {
        var match = fence_re.exec(line);
        if (match) {
            var fence = match[1];
            var lang = match[3];
            var handler = handler_for_fence(output_lines, fence, lang);
            handler_stack.push(handler);
        } else {
            output_lines.push(line);
        }
    };

    var current_handler = default_hander();
    handler_stack.push(current_handler);

    _.each(input, function (line) {
        var handler = handler_stack[handler_stack.length - 1];
        handler.handle_line(line);
    });

    // Clean up all trailing blocks by letting them
    // insert closing fences
    while (handler_stack.length !== 0) {
        var handler = handler_stack[handler_stack.length - 1];
        handler.done();
    }

    if (output.length > 2 && output[output.length - 2] !== '') {
        output.push('');
    }

    return output.join('\n');
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = fenced_code;
}

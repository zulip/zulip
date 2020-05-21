// Parsing routine that can be dropped in to message parsing
// and formats code blocks
//
// This supports arbitrarily nested code blocks as well as
// auto-completing code blocks missing a trailing close.

// See backend fenced_code.py:71 for associated regexp
const fencestr = "^(~{3,}|`{3,})"            + // Opening Fence
               "[ ]*"                      + // Spaces
               "("                         +
                   "\\{?\\.?"              +
                   "([a-zA-Z0-9_+-./#]*)"  + // Language
                   "\\}?"                  +
               "[ ]*"                      + // Spaces
               ")$";
const fence_re = new RegExp(fencestr);

// Default stashing function does nothing
let stash_func = function (text) {
    return text;
};

exports.wrap_code = function (code) {
    // Trim trailing \n until there's just one left
    // This mirrors how pygments handles code input
    return '<div class="codehilite"><pre><span></span><code>' +
        _.escape(code.replace(/^\n+|\n+$/g, '')) +
        '\n</code></pre></div>\n';
};

function wrap_quote(text) {
    const paragraphs = text.split('\n\n');
    const quoted_paragraphs = [];

    // Prefix each quoted paragraph with > at the
    // beginning of each line
    for (const paragraph of paragraphs) {
        const lines = paragraph.split('\n');
        quoted_paragraphs.push(lines.filter(line => line !== '').map(line => '> ' + line).join('\n'));
    }

    return quoted_paragraphs.join('\n\n');
}

function wrap_tex(tex) {
    try {
        return katex.renderToString(tex, {
            displayMode: true,
        });
    } catch (ex) {
        return '<span class="tex-error">' + _.escape(tex) + '</span>';
    }
}

exports.set_stash_func = function (stash_handler) {
    stash_func = stash_handler;
};

exports.process_fenced_code = function (content) {
    const input = content.split('\n');
    const output = [];
    const handler_stack = [];
    let consume_line;

    function handler_for_fence(output_lines, fence, lang) {
        // lang is ignored except for 'quote', as we
        // don't do syntax highlighting yet
        return (function () {
            const lines = [];
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
                        const text = wrap_quote(lines.join('\n'));
                        output_lines.push('');
                        output_lines.push(text);
                        output_lines.push('');
                        handler_stack.pop();
                    },
                };
            }

            if (lang === 'math') {
                return {
                    handle_line: function (line) {
                        if (line === fence) {
                            this.done();
                        } else {
                            lines.push(line);
                        }
                    },

                    done: function () {
                        const text = wrap_tex(lines.join('\n'));
                        const placeholder = stash_func(text, true);
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
                        lines.push(line.trimRight());
                    }
                },

                done: function () {
                    const text = exports.wrap_code(lines.join('\n'));
                    // insert safe HTML that is passed through the parsing
                    const placeholder = stash_func(text, true);
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
        const match = fence_re.exec(line);
        if (match) {
            const fence = match[1];
            const lang = match[3];
            const handler = handler_for_fence(output_lines, fence, lang);
            handler_stack.push(handler);
        } else {
            output_lines.push(line);
        }
    };

    const current_handler = default_hander();
    handler_stack.push(current_handler);

    for (const line of input) {
        const handler = handler_stack[handler_stack.length - 1];
        handler.handle_line(line);
    }

    // Clean up all trailing blocks by letting them
    // insert closing fences
    while (handler_stack.length !== 0) {
        const handler = handler_stack[handler_stack.length - 1];
        handler.done();
    }

    if (output.length > 2 && output[output.length - 2] !== '') {
        output.push('');
    }

    return output.join('\n');
};

const fence_length_re = /^ {0,3}(`{3,})/gm;
exports.get_unused_fence = (content) => {
    // we only return ``` fences, not ~~~.
    let length = 3;
    let match;
    fence_length_re.lastIndex = 0;
    while ((match = fence_length_re.exec(content)) !== null) {
        length = Math.max(length, match[1].length + 1);
    }
    return '`'.repeat(length);
};

window.fenced_code = exports;

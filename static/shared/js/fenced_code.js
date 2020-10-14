import katex from "katex";
import _ from "lodash";

// Parsing routine that can be dropped in to message parsing
// and formats code blocks
//
// This supports arbitrarily nested code blocks as well as
// auto-completing code blocks missing a trailing close.

// See backend fenced_code.py:71 for associated regexp
const fencestr =
    "^(~{3,}|`{3,})" + // Opening Fence
    "[ ]*" + // Spaces
    "(" +
    "\\{?\\.?" +
    "([a-zA-Z0-9_+-./#]*)" + // Language
    "\\}?" +
    ")" +
    "[ ]*" + // Spaces
    "(" +
    "\\{?\\.?" +
    "([^~`]*)" + // Header (see fenced_code.py)
    "\\}?" +
    ")" +
    "$";
const fence_re = new RegExp(fencestr);

// Default stashing function does nothing
let stash_func = function (text) {
    return text;
};

// We fill up the actual values when initializing.
let pygments_data = {};

export function initialize(generated_pygments_data) {
    pygments_data = generated_pygments_data.langs;
}

export function wrap_code(code, lang) {
    let header = '<div class="codehilite"><pre><span></span><code>';
    // Mimics the backend logic of adding a data-attribute (data-code-language)
    // to know what Pygments language was used to highlight this code block.
    //
    // NOTE: Clients like zulip-mobile wouldn't receive the pygments data since that comes from outside
    // the `/shared` folder. To handle such a case we check if pygments data is empty and fallback to
    // using the default header if it is.
    if (lang !== undefined && lang !== "" && Object.keys(pygments_data).length > 0) {
        const code_language = _.get(pygments_data, [lang, "pretty_name"], _.escape(lang));
        header = `<div class="codehilite" data-code-language="${code_language}"><pre><span></span><code>`;
    }
    // Trim trailing \n until there's just one left
    // This mirrors how pygments handles code input
    return header + _.escape(code.replace(/^\n+|\n+$/g, "")) + "\n</code></pre></div>\n";
}

function wrap_quote(text) {
    const paragraphs = text.split("\n\n");
    const quoted_paragraphs = [];

    // Prefix each quoted paragraph with > at the
    // beginning of each line
    for (const paragraph of paragraphs) {
        const lines = paragraph.split("\n");
        quoted_paragraphs.push(
            lines
                .filter((line) => line !== "")
                .map((line) => "> " + line)
                .join("\n"),
        );
    }

    return quoted_paragraphs.join("\n\n");
}

function wrap_tex(tex) {
    try {
        return katex.renderToString(tex, {
            displayMode: true,
        });
    } catch {
        return '<span class="tex-error">' + _.escape(tex) + "</span>";
    }
}

function wrap_spoiler(header, text, stash_func) {
    const output = [];
    const header_div_open_html = '<div class="spoiler-block"><div class="spoiler-header">';
    const end_header_start_content_html = '</div><div class="spoiler-content" aria-hidden="true">';
    const footer_html = "</div></div>";

    output.push(stash_func(header_div_open_html));
    output.push(header);
    output.push(stash_func(end_header_start_content_html));
    output.push(text);
    output.push(stash_func(footer_html));
    return output.join("\n\n");
}

export function set_stash_func(stash_handler) {
    stash_func = stash_handler;
}

export function process_fenced_code(content) {
    const input = content.split("\n");
    const output = [];
    const handler_stack = [];
    let consume_line;

    function handler_for_fence(output_lines, fence, lang, header) {
        // lang is ignored except for 'quote', as we
        // don't do syntax highlighting yet
        return (function () {
            const lines = [];
            if (lang === "quote") {
                return {
                    handle_line(line) {
                        if (line === fence) {
                            this.done();
                        } else {
                            consume_line(lines, line);
                        }
                    },

                    done() {
                        const text = wrap_quote(lines.join("\n"));
                        output_lines.push("");
                        output_lines.push(text);
                        output_lines.push("");
                        handler_stack.pop();
                    },
                };
            }

            if (lang === "math") {
                return {
                    handle_line(line) {
                        if (line === fence) {
                            this.done();
                        } else {
                            lines.push(line);
                        }
                    },

                    done() {
                        const text = wrap_tex(lines.join("\n"));
                        const placeholder = stash_func(text, true);
                        output_lines.push("");
                        output_lines.push(placeholder);
                        output_lines.push("");
                        handler_stack.pop();
                    },
                };
            }

            if (lang === "spoiler") {
                return {
                    handle_line(line) {
                        if (line === fence) {
                            this.done();
                        } else {
                            lines.push(line);
                        }
                    },

                    done() {
                        const text = wrap_spoiler(header, lines.join("\n"), stash_func);
                        output_lines.push("");
                        output_lines.push(text);
                        output_lines.push("");
                        handler_stack.pop();
                    },
                };
            }

            return {
                handle_line(line) {
                    if (line === fence) {
                        this.done();
                    } else {
                        lines.push(line.trimEnd());
                    }
                },

                done() {
                    const text = wrap_code(lines.join("\n"), lang);
                    // insert safe HTML that is passed through the parsing
                    const placeholder = stash_func(text, true);
                    output_lines.push("");
                    output_lines.push(placeholder);
                    output_lines.push("");
                    handler_stack.pop();
                },
            };
        })();
    }

    function default_hander() {
        return {
            handle_line(line) {
                consume_line(output, line);
            },
            done() {
                handler_stack.pop();
            },
        };
    }

    consume_line = function consume_line(output_lines, line) {
        const match = fence_re.exec(line);
        if (match) {
            const fence = match[1];
            const lang = match[3];
            const header = match[5];
            const handler = handler_for_fence(output_lines, fence, lang, header);
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

    if (output.length > 2 && output[output.length - 2] !== "") {
        output.push("");
    }

    return output.join("\n");
}

const fence_length_re = /^ {0,3}(`{3,})/gm;
export function get_unused_fence(content) {
    // we only return ``` fences, not ~~~.
    let length = 3;
    let match;
    fence_length_re.lastIndex = 0;
    while ((match = fence_length_re.exec(content)) !== null) {
        length = Math.max(length, match[1].length + 1);
    }
    return "`".repeat(length);
}

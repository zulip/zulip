/**
 * Fenced block preprocessor for the unified/mdast processor.
 *
 * Transforms ~~~quote blocks before micromark parsing, using the same
 * handler-stack architecture as fenced_code.ts to support arbitrary
 * nesting. ~~~math and ~~~spoiler blocks pass through as regular code
 * fences for micromark to parse, then get transformed in the mdast
 * phase (see markdown_zulip_transforms.ts). Regular code blocks also
 * pass through unchanged.
 */

import assert from "minimalistic-assert";

// Same regex as fenced_code.ts — see backend fenced_code.py:71
const fencestr =
    "^(~{3,}|`{3,})" + // Opening fence
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

type Handler = {
    handle_line: (line: string) => void;
    done: () => void;
};

function wrap_quote(text: string): string {
    const paragraphs = text.split("\n");
    const quoted_paragraphs = [];
    for (const paragraph of paragraphs) {
        const lines = paragraph.split("\n");
        quoted_paragraphs.push(lines.map((line) => "> " + line).join("\n"));
    }
    return quoted_paragraphs.join("\n");
}

export function preprocess_fenced_blocks(content: string): string {
    const input = content.split("\n");
    const output: string[] = [];
    const handler_stack: Handler[] = [];
    let consume_line: (lines: string[], line: string) => void;

    function handler_for_fence(
        output_lines: string[],
        opening_fence_line: string,
        fence: string,
        lang: string,
        _header: string,
    ): Handler {
        const lines: string[] = [];

        if (lang === "quote") {
            return {
                handle_line(line) {
                    if (line === fence) {
                        this.done();
                    } else {
                        // Allow nested fenced blocks inside quotes
                        consume_line(lines, line);
                    }
                },
                done() {
                    const text = wrap_quote(lines.join("\n"));
                    output_lines.push("", text, "");
                    handler_stack.pop();
                },
            };
        }

        // All other fenced blocks (math, spoiler, code, etc.) pass through
        // unchanged for micromark to parse as code fences. Math and spoiler
        // blocks are transformed in the mdast phase after parsing.
        return {
            handle_line(line) {
                if (line === fence) {
                    this.done();
                } else {
                    lines.push(line);
                }
            },
            done() {
                output_lines.push(opening_fence_line, ...lines, fence);
                handler_stack.pop();
            },
        };
    }

    function default_handler(): Handler {
        return {
            handle_line(line) {
                consume_line(output, line);
            },
            done() {
                handler_stack.pop();
            },
        };
    }

    consume_line = function consume_line(output_lines: string[], line: string) {
        const match = fence_re.exec(line);
        if (match) {
            const fence = match[1]!;
            const lang = match[3]!;
            const header = match[5]!;
            const handler = handler_for_fence(output_lines, line, fence, lang, header);
            handler_stack.push(handler);
        } else {
            output_lines.push(line);
        }
    };

    const current_handler = default_handler();
    handler_stack.push(current_handler);

    for (const line of input) {
        const handler = handler_stack.at(-1);
        assert(handler !== undefined, "Handler stack is empty.");
        handler.handle_line(line);
    }

    // Clean up unclosed blocks
    while (handler_stack.length > 0) {
        const handler = handler_stack.at(-1);
        handler!.done();
    }

    return output.join("\n");
}

"use strict";

export function trim_and_dedent(str) {
    const lines = str.split("\n");

    while (lines.length > 0 && lines[0].trim() === "") {
        lines.shift();
    }

    while (lines.length > 0 && lines.at(-1).trim() === "") {
        lines.pop();
    }

    if (lines.length === 0) {
        return "";
    }

    const ws_prefix = lines[0].match(/^\s*/)[0];

    const dedented = lines.map((line) => {
        if (line.trim() === "") {
            return "";
        }

        // Remove only the first line's indent
        return line.startsWith(ws_prefix) ? line.slice(ws_prefix.length) : "INDENT ERROR: " + line;
    });

    return dedented.join("\n");
}

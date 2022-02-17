"use strict";

/**
 * mdiff.js
 *
 * Used to produce colorful and informative diffs for comparison of generated
 * Markdown.  Unlike the built-in diffs used in python or node.js assert libraries,
 * is actually designed to be effective for long, single-line comparisons.
 *
 * Based on diffing library difflib, a js port of the python library.
 *
 * The sole exported function diff_strings(string_0, string_1) returns a pretty-printed
 * Unicode string containing their diff.
 */

const difflib = require("difflib");

function apply_color(input_string, changes) {
    let previous_index = 0;
    let processed_string = input_string.slice(0, 2);
    input_string = input_string.slice(2);

    const formatter = new Map([
        ["delete", (string) => "\u001B[31m" + string + "\u001B[0m"],
        ["insert", (string) => "\u001B[32m" + string + "\u001B[0m"],
        ["replace", (string) => "\u001B[33m" + string + "\u001B[0m"],
    ]);
    for (const change of changes) {
        if (formatter.has(change.tag)) {
            processed_string += input_string.slice(previous_index, change.beginning_index);
            processed_string += formatter.get(change.tag)(
                input_string.slice(change.beginning_index, change.ending_index),
            );
            previous_index = change.ending_index;
        }
    }

    processed_string += input_string.slice(previous_index);
    return processed_string;
}

/**
 * The library difflib produces diffs that look as follows:
 *
 * - <p>upgrade! yes</p>
 * ?    ^^     -
 * + <p>downgrade yes.</p>
 * ?    ^^^^         +
 *
 * The purpose of this function is to facilitate converting these diffs into
 * colored versions, where the question-mark lines are removed, replaced with
 * directions to add appropriate color to the lines that they annotate.
 */
function parse_questionmark_line(questionmark_line) {
    let current_sequence = ""; // Either "^", "-", "+", or ""
    let beginning_index = 0;
    let index = 0;

    const changes_list = [];
    const aliases = new Map([
        ["^", "replace"],
        ["+", "insert"],
        ["-", "delete"],
    ]);
    const add_change = () => {
        if (current_sequence) {
            changes_list.push({
                tag: aliases.get(current_sequence),
                beginning_index,
                ending_index: index,
            });
            current_sequence = "";
        }
    };

    questionmark_line = questionmark_line.slice(2).trimRight("\n");

    for (const character of questionmark_line) {
        if (aliases.has(character)) {
            if (current_sequence !== character) {
                add_change();
                current_sequence = character;
                beginning_index = index;
            }
        } else {
            add_change();
        }
        index += 1;
    }

    // In case we have a "change" involving the last character on a line
    // e.g. a string such as "? ^^  -- ++++"
    add_change();

    return changes_list;
}

function diff_strings(string_0, string_1) {
    let output_lines = [];
    let ndiff_output = "";
    let changes_list = [];

    ndiff_output = difflib.ndiff(string_0.split("\n"), string_1.split("\n"));

    for (const line of ndiff_output) {
        if (line.startsWith("+")) {
            output_lines.push(line);
        } else if (line.startsWith("-")) {
            output_lines.push(line);
        } else if (line.startsWith("?")) {
            changes_list = parse_questionmark_line(line);
            output_lines.push(apply_color(output_lines.pop(), changes_list));
        } else {
            output_lines.push(line);
        }
    }

    output_lines = output_lines.map(
        (string) => "\u001B[34m" + string.slice(0, 1) + "\u001B[0m" + string.slice(1),
    );

    return output_lines.join("\n");
}

module.exports = {diff_strings};

// Simple CLI for this module
// Only run this code if called as a command-line utility
if (require.main === module) {
    // First two args are just "node" and "mdiff.js"
    const argv = require("minimist")(process.argv.slice(2));

    if (Object.hasOwn(argv, "help")) {
        console.log(
            process.argv[0] +
                " " +
                process.argv[1] +
                " [ --help ]" +
                " string_0" +
                " string_1" +
                "\n" +
                "Where string_0 and string_1 are the strings to be diffed",
        );
    }

    const output = diff_strings(argv._[0], argv._[1]);
    console.log(output);
}

"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const blueslip_stacktrace = zrequire("blueslip_stacktrace");

run_test("clean_path", () => {
    // Local file
    assert.strictEqual(
        blueslip_stacktrace.clean_path("webpack:///web/src/upload.js"),
        "/web/src/upload.js",
    );

    // Third party library (jQuery)
    assert.strictEqual(
        blueslip_stacktrace.clean_path(
            "webpack:///.-npm-cache/de76fb6f582a29b053274f9048b6158091351048/node_modules/jquery/dist/jquery.js",
        ),
        "jquery/dist/jquery.js",
    );

    // Third party library (underscore)
    assert.strictEqual(
        blueslip_stacktrace.clean_path(
            "webpack:///.-npm-cache/de76fb6f582a29b053274f9048b…58091351048/node_modules/underscore/underscore.js",
        ),
        "underscore/underscore.js",
    );
});

run_test("clean_function_name", () => {
    assert.deepEqual(blueslip_stacktrace.clean_function_name(undefined), undefined);

    // Local file
    assert.deepEqual(
        blueslip_stacktrace.clean_function_name("Object../web/src/upload.js.exports.options"),
        {
            scope: "Object../web/src/upload.js.exports.",
            name: "options",
        },
    );

    // Third party library (jQuery)
    assert.deepEqual(blueslip_stacktrace.clean_function_name("mightThrow"), {
        scope: "",
        name: "mightThrow",
    });

    // Third party library (underscore)
    assert.deepEqual(
        blueslip_stacktrace.clean_function_name(
            "Function.../zulip-npm-cache/de76fb6f582a29b053274f…es/underscore/underscore.js?3817._.each._.forEach",
        ),
        {
            scope: "Function.../zulip-npm-cache/de76fb6f582a29b053274f…es/underscore/underscore.js?3817._.each._.",
            name: "forEach",
        },
    );
});

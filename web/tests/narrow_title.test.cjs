"use strict";

const assert = require("node:assert/strict");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

set_global("document", {title: ""});

const narrow_title = zrequire("narrow_title");
const {set_realm} = zrequire("state_data");

set_realm({realm_name: "Test org"});

run_test("overlay title replaces narrow title while set", () => {
    document.title = "";
    narrow_title.redraw_title();
    assert.equal(document.title, "home - Test org - Zulip");

    narrow_title.set_overlay_title("Settings");
    assert.equal(document.title, "Settings - Test org - Zulip");

    narrow_title.set_overlay_title(undefined);
    assert.equal(document.title, "home - Test org - Zulip");
});

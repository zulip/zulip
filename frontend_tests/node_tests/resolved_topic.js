"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const resolved_topic = zrequire("../shared/js/resolved_topic");

const topic_name = "asdf";
const resolved_name = "✔ " + topic_name;
const overresolved_name = "✔ ✔✔ " + topic_name;
const pseudoresolved_name = "✔" + topic_name; // check mark, but no space

run_test("is_resolved", () => {
    assert.ok(!resolved_topic.is_resolved(topic_name));
    assert.ok(resolved_topic.is_resolved(resolved_name));
    assert.ok(resolved_topic.is_resolved(overresolved_name));
    assert.ok(!resolved_topic.is_resolved(pseudoresolved_name));
});

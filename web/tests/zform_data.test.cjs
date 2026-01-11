"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {form_schema} = zrequire("zform_data");

run_test("schema rejects", () => {
    const bogus_data = {bogus_field: 99};
    const parse_result = form_schema.safeParse(bogus_data);
    assert.ok(!parse_result.success);
});

run_test("schema accepts choices", () => {
    const form_data = {
        type: "choices",
        heading: "What planet do we live on?",
        choices: [
            {
                type: "multiple_choice",
                short_name: "A",
                long_name: "Earth",
                reply: "answer QUIZ42 A",
            },
            {
                type: "multiple_choice",
                short_name: "B",
                long_name: "Jupiter",
                reply: "answer QUIZ42 B",
            },
        ],
    };
    const parse_result = form_schema.safeParse(form_data);
    assert.ok(parse_result.success);
    assert.deepEqual(parse_result.data, form_data);
});

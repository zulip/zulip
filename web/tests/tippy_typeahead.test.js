"use strict";

const {strict: assert} = require("assert");

const tippy = require("tippy.js");

const {mock_esm, zrequire} = require("./lib/namespace");
const {make_stub} = require("./lib/stub");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const tippy_typeahead = zrequire("tippy_typeahead");

run_test("initialize_tippy_typehead_test", ({override}) => {
    const commonly_used_pronouns = ["he/him", "she/her", "they/them"];
    let tippy_show_called;
    let tippy_hide_called;

    let my_content;
    override(tippy, "default", (element, options) => {
        assert.ok(element);
        assert.equal(options.content, my_content);
        return {
            setContent(c) {
                assert.equal(c, my_content);
            },
            show() {
                tippy_show_called = true;
            },
            hide() {
                tippy_hide_called = true;
            },
        };
    });
    const ui_util = mock_esm("../src/ui_util");
    ui_util.parse_html = (html) => html;

    const $pronouns_type_field = $.create(".pronouns_type_field");
    const $pronouns_type_field_parent = $.create(".pronouns_type_field_parent");
    const $tippy_typeahead_suggestion = $.create(".tippy-typeahead-suggestion");
    $tippy_typeahead_suggestion.text = () => "he/him";

    const stub = make_stub();
    $pronouns_type_field.get = stub.f;

    $pronouns_type_field_parent.on = (action, selector, defined_fn) => {
        if (action === "click" && selector === ".tippy-typeahead-suggestion") {
            $tippy_typeahead_suggestion.on("click", defined_fn);
        }
    };

    $pronouns_type_field.parent = () => $pronouns_type_field_parent;

    my_content =
        "<div>" +
        commonly_used_pronouns
            .map((match) => `<div class="tippy-typeahead-suggestion">${match}</div>`)
            .join("") +
        "</div>";
    tippy_typeahead.initTippyTypeahead($pronouns_type_field, commonly_used_pronouns);
    $pronouns_type_field.trigger("focus");
    assert.ok(tippy_show_called);

    $pronouns_type_field.val("unknown pronoun");
    $pronouns_type_field.trigger("input");
    assert.ok(tippy_hide_called);

    tippy_show_called = false;
    my_content = `<div><div class="tippy-typeahead-suggestion">he/him</div></div>`;
    $pronouns_type_field.val("he/him");
    $pronouns_type_field.trigger("input");
    assert.ok(tippy_show_called);

    tippy_hide_called = false;
    $tippy_typeahead_suggestion.trigger("click");
    assert.equal($pronouns_type_field.val(), "he/him");
    assert.ok(tippy_hide_called);
});

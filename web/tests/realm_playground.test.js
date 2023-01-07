"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const pygments_data = zrequire("../generated/pygments_data.json");

const realm_playground = zrequire("realm_playground");

run_test("get_pygments_typeahead_list_for_composebox", () => {
    // When no Code Playground is configured, the list of candidates should
    // include everything in pygments_data, but nothing more. Order doesn't
    // matter.
    let candidates = realm_playground.get_pygments_typeahead_list_for_composebox();
    assert.ok(Object.keys(pygments_data.langs).every((value) => candidates.includes(value)));
    assert.equal(candidates.length, Object.keys(pygments_data.langs).length);

    const custom_pygment_language = "Custom_lang";
    const playground_data = [
        {
            id: 2,
            name: "Custom Lang",
            pygments_language: custom_pygment_language,
            url_prefix: "https://example.com/?q=",
        },
    ];
    realm_playground.initialize(playground_data, pygments_data);

    // Verify that Code Playground's pygments_language shows up in the result.
    // As well as all of pygments_data. Order doesn't matter and the result
    // shouldn't include anything else.
    candidates = realm_playground.get_pygments_typeahead_list_for_composebox();
    assert.ok(Object.keys(pygments_data.langs).every((value) => candidates.includes(value)));
    assert.ok(candidates.includes(custom_pygment_language));
    assert.equal(
        candidates.length,
        Object.keys(pygments_data.langs).length + playground_data.length,
    );
});

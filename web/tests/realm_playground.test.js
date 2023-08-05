"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const pygments_data = zrequire("../generated/pygments_data.json");

const {$t} = zrequire("i18n");
const realm_playground = zrequire("realm_playground");
const typeahead_helper = zrequire("typeahead_helper");

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
            url_template: "https://example.com/?q={code}",
        },
    ];
    realm_playground.initialize({
        playground_data,
        pygments_comparator_func: typeahead_helper.compare_language,
    });

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

run_test("get_pygments_typeahead_list_for_settings", () => {
    const custom_pygment_language = "custom_lang";
    const playground_data = [
        {
            id: 1,
            name: "Custom Lang #1",
            pygments_language: custom_pygment_language,
            url_template: "https://example.com/?q={code}",
        },
        {
            id: 2,
            name: "Custom Lang #2",
            pygments_language: custom_pygment_language,
            url_template: "https://example.com/?q={code}",
        },
        {
            id: 3,
            name: "Invent a Language",
            pygments_language: "invent_a_lang",
            url_template: "https://example.com/?q={code}",
        },
    ];
    realm_playground.initialize({
        playground_data,
        pygments_comparator_func: typeahead_helper.compare_language,
    });

    let candidates = realm_playground.get_pygments_typeahead_list_for_settings("");
    let iterator = candidates.entries();
    assert.equal(iterator.next().value[1], $t({defaultMessage: "Custom language: custom_lang"}));
    assert.equal(iterator.next().value[1], $t({defaultMessage: "Custom language: invent_a_lang"}));
    assert.equal(iterator.next().value[1], "JavaScript (javascript, js, javascript, js)");
    assert.equal(
        iterator.next().value[1],
        "Python (python, py, py3, python3, sage, python, py, py3, python3, sage)",
    );
    assert.equal(iterator.next().value[1], "Java (java, java)");
    assert.equal(iterator.next().value[1], "Go (go, golang, go, golang)");
    assert.equal(iterator.next().value[1], "Rust (rust, rs, rust, rs)");

    // Test typing "cu". Previously added custom languages should show up too.
    candidates = realm_playground.get_pygments_typeahead_list_for_settings("cu");
    iterator = candidates.entries();
    assert.equal(
        iterator.next().value[1],
        $t({defaultMessage: "Custom language: {query}"}, {query: "cu"}),
    );
    assert.equal(iterator.next().value[1], $t({defaultMessage: "Custom language: custom_lang"}));
    assert.equal(iterator.next().value[1], $t({defaultMessage: "Custom language: invent_a_lang"}));
    assert.equal(iterator.next().value[1], "JavaScript (javascript, js, javascript, js)");
    assert.equal(
        iterator.next().value[1],
        "Python (python, py, py3, python3, sage, python, py, py3, python3, sage)",
    );

    // Test typing "invent_a_lang". Make sure there is no duplicate entries.
    candidates = realm_playground.get_pygments_typeahead_list_for_settings("invent_a_lang");
    iterator = candidates.entries();
    assert.equal(iterator.next().value[1], $t({defaultMessage: "Custom language: invent_a_lang"}));
    assert.equal(iterator.next().value[1], $t({defaultMessage: "Custom language: custom_lang"}));
    assert.equal(iterator.next().value[1], "JavaScript (javascript, js, javascript, js)");
    assert.equal(
        iterator.next().value[1],
        "Python (python, py, py3, python3, sage, python, py, py3, python3, sage)",
    );
});

"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const narrow_state = mock_esm("../src/narrow_state");
const search_suggestion = mock_esm("../src/search_suggestion");

const Filter = {};

mock_esm("../src/filter", {
    Filter,
});

const search = zrequire("search");

run_test("clear_search_form", () => {
    $("#search_query").val("noise");
    $("#search_query").trigger("focus");

    search.clear_search_form();

    assert.equal($("#search_query").is_focused(), false);
    assert.equal($("#search_query").val(), "");
});

run_test("initialize", ({mock_template}) => {
    const $search_query_box = $("#search_query");
    const $searchbox_form = $("#searchbox_form");

    mock_template("search_list_item.hbs", true, (data, html) => {
        assert.equal(typeof data.description_html, "string");
        if (data.is_person) {
            assert.equal(typeof data.user_pill_context.id, "number");
            assert.equal(typeof data.user_pill_context.display_value, "string");
            assert.equal(typeof data.user_pill_context.has_image, "boolean");
            assert.equal(typeof data.user_pill_context.img_src, "string");
        }
        return html;
    });

    search_suggestion.max_num_of_search_results = 999;
    let operators;

    $search_query_box.typeahead = (opts) => {
        assert.equal(opts.items, 999);
        assert.equal(opts.naturalSearch, true);
        assert.equal(opts.helpOnEmptyStrings, true);
        assert.equal(opts.matcher(), true);

        {
            const search_suggestions = {
                lookup_table: new Map([
                    [
                        "stream:Verona",
                        {
                            description_html: "Stream <strong>Ver</strong>ona",
                            search_string: "stream:Verona",
                        },
                    ],
                    [
                        "ver",
                        {
                            description_html: "Search for ver",
                            search_string: "ver",
                        },
                    ],
                ]),
                strings: ["ver", "stream:Verona"],
            };

            /* Test source */
            search_suggestion.get_suggestions = () => search_suggestions;
            const expected_source_value = search_suggestions.strings;
            const source = opts.source("ver");
            assert.equal(source, expected_source_value);

            /* Test highlighter */
            let expected_value = `<div class="search_list_item">\n    <span>Search for ver</span>\n</div>\n`;
            assert.equal(opts.highlighter(source[0]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>Stream <strong>Ver</strong>ona</span>\n</div>\n`;
            assert.equal(opts.highlighter(source[1]), expected_value);

            /* Test sorter */
            assert.equal(opts.sorter(search_suggestions.strings), search_suggestions.strings);
        }

        {
            const search_suggestions = {
                lookup_table: new Map([
                    [
                        "dm-including:zo",
                        {
                            description_html: "group direct messages including",
                            is_person: true,
                            search_string: "dm-including:user7@zulipdev.com",
                            user_pill_context: {
                                display_value: "<strong>Zo</strong>e",
                                has_image: true,
                                id: 7,
                                img_src:
                                    "https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d=identicon&version=1&s=50",
                            },
                        },
                    ],
                    [
                        "dm:zo",
                        {
                            description_html: "direct messages with",
                            is_person: true,
                            search_string: "dm:user7@zulipdev.com",
                            user_pill_context: {
                                display_value: "<strong>Zo</strong>e",
                                has_image: true,
                                id: 7,
                                img_src:
                                    "https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d=identicon&version=1&s=50",
                            },
                        },
                    ],
                    [
                        "sender:zo",
                        {
                            description_html: "sent by",
                            is_person: true,
                            search_string: "sender:user7@zulipdev.com",
                            user_pill_context: {
                                display_value: "<strong>Zo</strong>e",
                                has_image: true,
                                id: 7,
                                img_src:
                                    "https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d=identicon&version=1&s=50",
                            },
                        },
                    ],
                    [
                        "zo",
                        {
                            description_html: "Search for zo",
                            search_string: "zo",
                        },
                    ],
                ]),
                strings: ["zo", "sender:zo", "dm:zo", "dm-including:zo"],
            };

            /* Test source */
            search_suggestion.get_suggestions = () => search_suggestions;
            const expected_source_value = search_suggestions.strings;
            const source = opts.source("zo");
            assert.equal(source, expected_source_value);

            /* Test highlighter */
            let expected_value = `<div class="search_list_item">\n    <span>Search for zo</span>\n</div>\n`;
            assert.equal(opts.highlighter(source[0]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>sent by</span>\n    <span class="pill-container pill-container-btn">\n        <div class='pill ' tabindex=0>\n    <img class="pill-image" src="https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d&#x3D;identicon&amp;version&#x3D;1&amp;s&#x3D;50" />\n    <span class="pill-value">&lt;strong&gt;Zo&lt;/strong&gt;e</span>\n    <div class="exit">\n        <span aria-hidden="true">&times;</span>\n    </div>\n</div>\n    </span>\n</div>\n`;
            assert.equal(opts.highlighter(source[1]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>direct messages with</span>\n    <span class="pill-container pill-container-btn">\n        <div class='pill ' tabindex=0>\n    <img class="pill-image" src="https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d&#x3D;identicon&amp;version&#x3D;1&amp;s&#x3D;50" />\n    <span class="pill-value">&lt;strong&gt;Zo&lt;/strong&gt;e</span>\n    <div class="exit">\n        <span aria-hidden="true">&times;</span>\n    </div>\n</div>\n    </span>\n</div>\n`;
            assert.equal(opts.highlighter(source[2]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>group direct messages including</span>\n    <span class="pill-container pill-container-btn">\n        <div class='pill ' tabindex=0>\n    <img class="pill-image" src="https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d&#x3D;identicon&amp;version&#x3D;1&amp;s&#x3D;50" />\n    <span class="pill-value">&lt;strong&gt;Zo&lt;/strong&gt;e</span>\n    <div class="exit">\n        <span aria-hidden="true">&times;</span>\n    </div>\n</div>\n    </span>\n</div>\n`;
            assert.equal(opts.highlighter(source[3]), expected_value);

            /* Test sorter */
            assert.equal(opts.sorter(search_suggestions.strings), search_suggestions.strings);
        }

        {
            let is_blurred;
            $search_query_box.on("blur", () => {
                is_blurred = true;
            });
            /* Test updater */
            const _setup = (search_box_val) => {
                is_blurred = false;
                $search_query_box.val(search_box_val);
                Filter.parse = (search_string) => {
                    assert.equal(search_string, search_box_val);
                    return operators;
                };
            };

            operators = [
                {
                    negated: false,
                    operator: "search",
                    operand: "ver",
                },
            ];
            _setup("ver");
            assert.equal(opts.updater("ver"), "ver");
            assert.ok(is_blurred);

            operators = [
                {
                    negated: false,
                    operator: "stream",
                    operand: "Verona",
                },
            ];
            _setup("stream:Verona");
            assert.equal(opts.updater("stream:Verona"), "stream:Verona");
            assert.ok(is_blurred);

            search.__Rewire__("is_using_input_method", true);
            _setup("stream:Verona");
            assert.equal(opts.updater("stream:Verona"), "stream:Verona");
            assert.ok(!is_blurred);

            $search_query_box.off("blur");
        }
    };

    search.initialize({
        on_narrow_search(raw_operators, options) {
            assert.deepEqual(raw_operators, operators);
            assert.deepEqual(options, {trigger: "search"});
        },
    });

    $search_query_box.val("test string");
    narrow_state.search_string = () => "ver";
    $search_query_box.trigger("blur");
    assert.equal($search_query_box.val(), "test string");

    search.__Rewire__("is_using_input_method", false);
    $searchbox_form.trigger("compositionend");
    assert.ok(search.is_using_input_method);

    const keydown = $searchbox_form.get_on_handler("keydown");
    let default_prevented = false;
    let ev = {
        type: "keydown",
        which: 15,
        preventDefault() {
            default_prevented = true;
        },
    };
    $search_query_box.is = () => false;
    assert.equal(keydown(ev), undefined);
    assert.ok(!default_prevented);

    ev.key = "Enter";
    assert.equal(keydown(ev), undefined);
    assert.ok(!default_prevented);

    ev.key = "Enter";
    $search_query_box.is = () => true;
    assert.equal(keydown(ev), undefined);
    assert.ok(default_prevented);

    ev = {
        type: "keyup",
    };
    let is_blurred;
    $search_query_box.off("blur");
    $search_query_box.on("blur", () => {
        is_blurred = true;
    });

    const _setup = (search_box_val) => {
        is_blurred = false;
        $search_query_box.val(search_box_val);
        Filter.parse = (search_string) => {
            assert.equal(search_string, search_box_val);
            return operators;
        };
    };

    operators = [
        {
            negated: false,
            operator: "search",
            operand: "",
        },
    ];
    _setup("");

    ev.key = "a";
    /* istanbul ignore next */
    $search_query_box.is = () => false;
    $searchbox_form.trigger(ev);

    assert.ok(!is_blurred);

    ev.key = "Enter";
    $search_query_box.is = () => false;
    $searchbox_form.trigger(ev);

    assert.ok(!is_blurred);

    ev.key = "Enter";
    $search_query_box.is = () => true;
    $searchbox_form.trigger(ev);
    assert.ok(is_blurred);

    _setup("ver");
    search.__Rewire__("is_using_input_method", true);
    $searchbox_form.trigger(ev);
    // No change on Enter keyup event when using input tool
    assert.ok(!is_blurred);

    _setup("ver");
    ev.key = "Enter";
    $search_query_box.is = () => true;
    $searchbox_form.trigger(ev);
    assert.ok(is_blurred);
});

run_test("initiate_search", () => {
    // open typeahead and select text when navbar is open
    // this implicitly expects the code to used the chained
    // function calls, which is something to keep in mind if
    // this test ever fails unexpectedly.
    narrow_state.filter = () => ({is_search: () => true});
    let typeahead_forced_open = false;
    let is_searchbox_text_selected = false;
    $("#search_query").typeahead = (lookup) => {
        if (lookup === "lookup") {
            typeahead_forced_open = true;
        }
        return $("#search_query");
    };
    $("#search_query").on("select", () => {
        is_searchbox_text_selected = true;
    });

    search.initiate_search();
    assert.ok(typeahead_forced_open);
    assert.ok(is_searchbox_text_selected);
    assert.equal($("#search_query").val(), "ver");

    // test that we append space for user convenience
    narrow_state.filter = () => ({is_search: () => false});
    search.initiate_search();
    assert.equal($("#search_query").val(), "ver ");
});

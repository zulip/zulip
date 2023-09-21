"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test, noop} = require("./lib/test");
const $ = require("./lib/zjquery");

const search_suggestion = mock_esm("../src/search_suggestion");

const search = zrequire("search");
const search_pill = zrequire("search_pill");
const {Filter} = zrequire("filter");

function stub_pills() {
    const $pill_container = $("#searchbox-input-container.pill-container");
    const $pill_input = $.create("pill_input");
    $pill_container.set_find_results(".input", $pill_input);
    $pill_input.before = noop;
}

run_test("clear_search_form", () => {
    $("#search_query").text("noise");
    $("#search_query").trigger("click");

    search.clear_search_form();

    assert.equal($("#search_query").is_focused(), false);
    assert.equal($("#search_query").text(), "");
});

run_test("initialize", ({override_rewire, mock_template}) => {
    const $search_query_box = $("#search_query");
    const $searchbox_form = $("#searchbox_form");
    stub_pills();

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

    let expected_suggestion_parts = [];
    mock_template("search_description.hbs", false, (data, html) => {
        assert.deepStrictEqual(data.parts, expected_suggestion_parts);
        return html;
    });
    let expected_pill_display_value = "";
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(data.display_value, expected_pill_display_value);
        return html;
    });

    search_suggestion.max_num_of_search_results = 999;
    let operators;

    $search_query_box.typeahead = (opts) => {
        assert.equal(opts.items, 999);
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
            assert.deepStrictEqual(source, expected_source_value);

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
            assert.deepStrictEqual(source, expected_source_value);

            /* Test highlighter */
            let expected_value = `<div class="search_list_item">\n    <span>Search for zo</span>\n</div>\n`;
            assert.equal(opts.highlighter(source[0]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>sent by</span>\n    <span class="pill-container pill-container-btn">\n        <div class='pill ' tabindex=0>\n    <img class="pill-image" src="https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d&#x3D;identicon&amp;version&#x3D;1&amp;s&#x3D;50" />\n    <span class="pill-label">\n        <span class="pill-value">&lt;strong&gt;Zo&lt;/strong&gt;e</span></span>\n    <div class="exit">\n        <span aria-hidden="true">&times;</span>\n    </div>\n</div>\n    </span>\n</div>\n`;
            assert.equal(opts.highlighter(source[1]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>direct messages with</span>\n    <span class="pill-container pill-container-btn">\n        <div class='pill ' tabindex=0>\n    <img class="pill-image" src="https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d&#x3D;identicon&amp;version&#x3D;1&amp;s&#x3D;50" />\n    <span class="pill-label">\n        <span class="pill-value">&lt;strong&gt;Zo&lt;/strong&gt;e</span></span>\n    <div class="exit">\n        <span aria-hidden="true">&times;</span>\n    </div>\n</div>\n    </span>\n</div>\n`;
            assert.equal(opts.highlighter(source[2]), expected_value);

            expected_value = `<div class="search_list_item">\n    <span>group direct messages including</span>\n    <span class="pill-container pill-container-btn">\n        <div class='pill ' tabindex=0>\n    <img class="pill-image" src="https://secure.gravatar.com/avatar/0f030c97ab51312c7bbffd3966198ced?d&#x3D;identicon&amp;version&#x3D;1&amp;s&#x3D;50" />\n    <span class="pill-label">\n        <span class="pill-value">&lt;strong&gt;Zo&lt;/strong&gt;e</span></span>\n    <div class="exit">\n        <span aria-hidden="true">&times;</span>\n    </div>\n</div>\n    </span>\n</div>\n`;
            assert.equal(opts.highlighter(source[3]), expected_value);

            /* Test sorter */
            assert.equal(opts.sorter(search_suggestions.strings), search_suggestions.strings);
        }

        {
            /* Test updater */
            const _setup = (search_box_val) => {
                $search_query_box.text(search_box_val);
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
            expected_suggestion_parts = [
                {
                    operand: "ver",
                    prefix_for_operator: "search for",
                    type: "prefix_for_operator",
                },
            ];
            expected_pill_display_value = "ver";
            assert.equal(opts.updater("ver"), "ver");

            operators = [
                {
                    negated: false,
                    operator: "stream",
                    operand: "Verona",
                },
            ];
            _setup("stream:Verona");
            expected_suggestion_parts = [
                {
                    type: "prefix_for_operator",
                    prefix_for_operator: "stream",
                    operand: "Verona",
                },
            ];
            expected_pill_display_value = "stream:Verona";
            assert.equal(opts.updater("stream:Verona"), "stream:Verona");

            search.__Rewire__("is_using_input_method", true);
            _setup("stream:Verona");
            assert.equal(opts.updater("stream:Verona"), "stream:Verona");
        }
        return {};
    };

    search.initialize({
        on_narrow_search() {},
    });

    $search_query_box.text("test string");

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

    const _setup = (search_box_val) => {
        const pills = search.search_pill_widget._get_pills_for_testing();
        for (const pill of pills) {
            pill.$element.remove = noop;
        }
        search.search_pill_widget.clear(true);

        Filter.parse = (search_string) => {
            assert.equal(search_string, search_box_val);
            return operators;
        };
        $search_query_box.text(search_box_val);
        search_pill.append_search_string(search_box_val, search.search_pill_widget);
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

    let search_exited = false;
    override_rewire(search, "exit_search", () => {
        search_exited = true;
    });

    ev.key = "Enter";
    $search_query_box.is = () => false;
    $searchbox_form.trigger(ev);
    assert.ok(!search_exited);

    ev.key = "Enter";
    $search_query_box.is = () => true;
    $searchbox_form.trigger(ev);
    assert.ok(search_exited);

    _setup("ver");
    ev.key = "Enter";
    // TODO(evy): is this still relevant or is_using_input_method be removed?
    search.__Rewire__("is_using_input_method", true);
    $searchbox_form.trigger(ev);

    search_exited = false;
    $searchbox_form.trigger(ev);
    assert.ok(search_exited);
});

run_test("initiate_search", ({override_rewire}) => {
    // open typeahead and select text when navbar is open
    // this implicitly expects the code to used the chained
    // function calls, which is something to keep in mind if
    // this test ever fails unexpectedly.
    let typeahead_forced_open = false;
    let is_searchbox_text_selected = false;
    let search_bar_opened = false;
    override_rewire(search, "open_search_bar_and_close_narrow_description", () => {
        search_bar_opened = true;
    });
    $("#search_query").typeahead = (lookup) => {
        if (lookup === "lookup") {
            typeahead_forced_open = true;
        }
        return $("#search_query");
    };
    $("#search_query").on("select", () => {
        is_searchbox_text_selected = true;
    });

    $(".navbar-search.expanded").length = 0;
    $("#search_query").text("");
    search.initiate_search();
    assert.ok(typeahead_forced_open);
    assert.ok(is_searchbox_text_selected);
    assert.ok(search_bar_opened);
    assert.equal($("#search_query").text(), "");
});

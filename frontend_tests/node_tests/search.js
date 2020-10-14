"use strict";

set_global("page_params", {
    search_pills_enabled: true,
});
zrequire("search");
zrequire("search_pill");
zrequire("Filter", "js/filter");
zrequire("message_view_header");

const noop = () => {};
const return_true = () => true;
const return_false = () => false;

set_global("$", global.make_zjquery());
set_global("narrow_state", {filter: return_false});
set_global("search_suggestion", {});
set_global("ui_util", {
    change_tab_to: noop,
    place_caret_at_end: noop,
});
set_global("narrow", {});
set_global("search_pill_widget", {
    widget: {
        getByID: return_true,
    },
});

global.patch_builtin("setTimeout", (func) => func());

run_test("clear_search_form", () => {
    $("#search_query").val("noise");
    $("#search_query").trigger("focus");
    $(".search_button").prop("disabled", false);

    search.clear_search_form();

    assert.equal($("#search_query").is_focused(), false);
    assert.equal($("#search_query").val(), "");
    assert.equal($(".search_button").prop("disabled"), true);
});

run_test("update_button_visibility", () => {
    const search_query = $("#search_query");
    const search_button = $(".search_button");

    search_query.is = return_false;
    search_query.val("");
    narrow_state.active = return_false;
    search_button.prop("disabled", true);
    search.update_button_visibility();
    assert(search_button.prop("disabled"));

    search_query.is = return_true;
    search_query.val("");
    narrow_state.active = return_false;
    search_button.prop("disabled", true);
    search.update_button_visibility();
    assert(!search_button.prop("disabled"));

    search_query.is = return_false;
    search_query.val("Test search term");
    narrow_state.active = return_false;
    search_button.prop("disabled", true);
    search.update_button_visibility();
    assert(!search_button.prop("disabled"));

    search_query.is = return_false;
    search_query.val("");
    narrow_state.active = return_true;
    search_button.prop("disabled", true);
    search.update_button_visibility();
    assert(!search_button.prop("disabled"));
});

run_test("initialize", () => {
    const search_query_box = $("#search_query");
    const searchbox_form = $("#searchbox_form");
    const search_button = $(".search_button");
    const searchbox = $("#searchbox");

    search_pill.get_search_string_for_current_filter = function () {
        return "is:starred";
    };

    search_suggestion.max_num_of_search_results = 99;
    search_query_box.typeahead = (opts) => {
        assert.equal(opts.fixed, true);
        assert.equal(opts.items, 99);
        assert.equal(opts.naturalSearch, true);
        assert.equal(opts.helpOnEmptyStrings, true);
        assert.equal(opts.matcher(), true);
        opts.on_move();

        {
            const search_suggestions = {
                lookup_table: new Map([
                    [
                        "stream:Verona",
                        {
                            description: "Stream <strong>Ver</strong>ona",
                            search_string: "stream:Verona",
                        },
                    ],
                    [
                        "ver",
                        {
                            description: "Search for ver",
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
            let expected_value = "Search for ver";
            assert.equal(opts.highlighter(source[0]), expected_value);

            expected_value = "Stream <strong>Ver</strong>ona";
            assert.equal(opts.highlighter(source[1]), expected_value);

            /* Test sorter */
            assert.equal(opts.sorter(search_suggestions.strings), search_suggestions.strings);
        }

        {
            let operators;
            let is_blurred;
            let is_append_search_string_called;
            search_query_box.on("blur", () => {
                is_blurred = true;
            });
            search_pill.append_search_string = () => {
                is_append_search_string_called = true;
            };
            /* Test updater */
            const _setup = (search_box_val) => {
                is_blurred = false;
                is_append_search_string_called = false;
                search_query_box.val(search_box_val);
                Filter.parse = (search_string) => {
                    assert.equal(search_string, search_box_val);
                    return operators;
                };
                narrow.activate = (raw_operators, options) => {
                    assert.deepEqual(raw_operators, operators);
                    assert.deepEqual(options, {trigger: "search"});
                };
                search_pill.get_search_string_for_current_filter = () => search_box_val;
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
            assert(!is_blurred);
            assert(is_append_search_string_called);

            operators = [
                {
                    negated: false,
                    operator: "stream",
                    operand: "Verona",
                },
            ];
            _setup("stream:Verona");

            assert.equal(opts.updater("stream:Verona"), "stream:Verona");
            assert(!is_blurred);
            assert(is_append_search_string_called);

            search.is_using_input_method = true;
            _setup("stream:Verona");

            assert.equal(opts.updater("stream:Verona"), "stream:Verona");
            assert(!is_blurred);
            assert(is_append_search_string_called);

            search_query_box.off("blur");
        }
    };

    search.initialize();

    const search_pill_stub = $.create(".pill");
    search_pill_stub.closest = () => ({data: noop});
    const stub_event = {
        relatedTarget: search_pill_stub,
    };
    search_query_box.val("test string");
    narrow_state.search_string = () => "ver";
    search_query_box.trigger($.Event("blur", stub_event));
    assert.equal(search_query_box.val(), "test string");

    searchbox.css({"box-shadow": "inset 0px 0px 0px 2px hsl(204, 20%, 74%)"});
    searchbox.trigger("focusout");
    assert.deepEqual(searchbox.css(), {"box-shadow": "unset"});

    search.is_using_input_method = false;
    searchbox_form.trigger("compositionend");
    assert(search.is_using_input_method);

    const keydown = searchbox_form.get_on_handler("keydown");
    let default_prevented = false;
    let ev = {
        type: "keydown",
        which: 15,
        preventDefault() {
            default_prevented = true;
        },
    };
    search_query_box.is = return_false;
    assert.equal(keydown(ev), undefined);
    assert(!default_prevented);

    ev.which = 13;
    assert.equal(keydown(ev), undefined);
    assert(!default_prevented);

    ev.which = 13;
    search_query_box.is = return_true;
    assert.equal(keydown(ev), undefined);
    assert(default_prevented);

    let operators;
    let is_blurred;
    narrow_state.active = return_false;
    search_query_box.off("blur");
    search_query_box.on("blur", () => {
        is_blurred = true;
    });

    const _setup = (search_box_val) => {
        is_blurred = false;
        search_button.prop("disabled", false);
        search_query_box.val(search_box_val);
        Filter.parse = (search_string) => {
            assert.equal(search_string, search_box_val);
            return operators;
        };
        narrow.activate = (raw_operators, options) => {
            assert.deepEqual(raw_operators, operators);
            assert.deepEqual(options, {trigger: "search"});
        };
        search_pill.get_search_string_for_current_filter = () => search_box_val;
    };

    operators = [
        {
            negated: false,
            operator: "search",
            operand: "",
        },
    ];
    _setup("");

    ev = {
        type: "keyup",
        which: 15,
    };
    search_query_box.is = return_false;
    searchbox_form.trigger(ev);

    assert(!is_blurred);
    assert(!search_button.prop("disabled"));

    ev.which = 13;
    search_query_box.is = return_false;
    searchbox_form.trigger(ev);

    assert(!is_blurred);
    assert(!search_button.prop("disabled"));

    ev.which = 13;
    search_query_box.is = return_true;
    searchbox_form.trigger(ev);
    assert(is_blurred);

    _setup("ver");
    search.is_using_input_method = true;
    searchbox_form.trigger(ev);
    // No change on Enter keyup event when using input tool
    assert(!is_blurred);
    assert(!search_button.prop("disabled"));

    _setup("ver");
    ev.which = 13;
    search_query_box.is = return_true;
    searchbox_form.trigger(ev);
    assert(is_blurred);
    assert(!search_button.prop("disabled"));

    search_button.prop("disabled", true);
    search_query_box.trigger("focus");
    assert(!search_button.prop("disabled"));
});

run_test("initiate_search", () => {
    // open typeahead and select text when navbar is open
    // this implicitly expects the code to used the chained
    // function calls, which is something to keep in mind if
    // this test ever fails unexpectedly.
    let typeahead_forced_open = false;
    let is_searchbox_text_selected = false;
    let is_searchbox_focused = false;
    $("#search_query").off("focus");
    $("#search_query").on("focus", () => {
        is_searchbox_focused = true;
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

    search.initiate_search();
    assert(typeahead_forced_open);
    assert(is_searchbox_text_selected);
    assert(is_searchbox_focused);
});

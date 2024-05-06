"use strict";

const {strict: assert} = require("assert");

const {zrequire, mock_esm} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

const noop = function () {};

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");

const input_pill = zrequire("input_pill");
const pill_typeahead = zrequire("pill_typeahead");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const user_groups = zrequire("user_groups");
const typeahead_helper = zrequire("typeahead_helper");

// set global test variables.
let sort_recipients_called = false;
let sort_streams_called = false;
const $fake_rendered_person = $.create("fake-rendered-person");
const $fake_rendered_stream = $.create("fake-rendered-stream");
const $fake_rendered_group = $.create("fake-rendered-group");

function override_typeahead_helper(override_rewire) {
    override_rewire(typeahead_helper, "render_person", () => $fake_rendered_person);
    override_rewire(typeahead_helper, "render_user_group", () => $fake_rendered_group);
    override_rewire(typeahead_helper, "render_stream", () => $fake_rendered_stream);
    override_rewire(typeahead_helper, "sort_streams", () => {
        sort_streams_called = true;
    });
    override_rewire(typeahead_helper, "sort_recipients", () => {
        sort_recipients_called = true;
    });
}

function user_item(user) {
    return {
        ...user,
        type: "user",
    };
}

const jill = {
    email: "jill@zulip.com",
    user_id: 10,
    full_name: "Jill Hill",
};
const jill_item = user_item(jill);
const mark = {
    email: "mark@zulip.com",
    user_id: 20,
    full_name: "Marky Mark",
};
const mark_item = user_item(mark);
const fred = {
    email: "fred@zulip.com",
    user_id: 30,
    full_name: "Fred Flintstone",
};
const fred_item = user_item(fred);
const me = {
    email: "me@example.com",
    user_id: 40,
    full_name: "me",
};
const me_item = user_item(me);

const persons = [jill, mark, fred, me];
for (const person of persons) {
    people.add_active_user(person);
}
const person_items = persons.map((person) => user_item(person));

function user_group_item(user_group) {
    return {
        ...user_group,
        type: "user_group",
    };
}

const admins = {
    name: "Admins",
    description: "foo",
    id: 1,
    members: [jill.user_id, mark.user_id],
};
const admins_item = user_group_item(admins);
const testers = {
    name: "Testers",
    description: "bar",
    id: 2,
    members: [mark.user_id, fred.user_id, me.user_id],
};
const testers_item = user_group_item(testers);

const groups = [admins, testers];
for (const group of groups) {
    user_groups.add(group);
}
const group_items = [admins_item, testers_item];

function stream_item(stream) {
    return {
        ...stream,
        type: "stream",
    };
}

const denmark = {
    stream_id: 1,
    name: "Denmark",
    subscribed: true,
    render_subscribers: true,
};
const denmark_item = stream_item(denmark);
peer_data.set_subscribers(denmark.stream_id, [me.user_id, mark.user_id]);

const sweden = {
    stream_id: 2,
    name: "Sweden",
    subscribed: false,
};
const sweden_item = stream_item(sweden);
peer_data.set_subscribers(sweden.stream_id, [mark.user_id, jill.user_id]);

const subs = [denmark, sweden];
for (const sub of subs) {
    stream_data.add_sub(sub);
}

run_test("set_up", ({mock_template, override, override_rewire}) => {
    override_typeahead_helper(override_rewire);
    mock_template("input_pill.hbs", true, (data, html) => {
        assert.equal(typeof data.display_value, "string");
        assert.equal(typeof data.has_image, "boolean");
        return html;
    });
    let input_pill_typeahead_called = false;
    const $fake_input = $.create(".input");
    $fake_input.before = noop;

    const $container = $.create(".pill-container");
    $container.find = () => $fake_input;

    const $pill_widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
    });

    let update_func_called = false;
    function update_func() {
        update_func_called = true;
    }

    let opts = {};
    override(bootstrap_typeahead, "Typeahead", (input_element, config) => {
        assert.equal(input_element.$element, $fake_input);
        assert.equal(config.items, 5);
        assert.ok(config.fixed);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.highlighter_html, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // test queries
        const stream_query = "#Denmark";
        const person_query = "me";
        const group_query = "test";

        (function test_highlighter() {
            if (opts.stream) {
                // Test stream highlighter_html for widgets that allow stream pills.
                assert.equal(
                    config.highlighter_html(denmark_item, stream_query),
                    $fake_rendered_stream,
                );
            }
            if (opts.user_group && opts.user) {
                // If user is also allowed along with user_group
                // then we should check that each of them rendered correctly.
                assert.equal(
                    config.highlighter_html(testers_item, group_query),
                    $fake_rendered_group,
                );
                assert.equal(config.highlighter_html(me_item, person_query), $fake_rendered_person);
            }
            if (opts.user && !opts.user_group) {
                assert.equal(config.highlighter_html(me_item, person_query), $fake_rendered_person);
            }
            if (!opts.user && opts.user_group) {
                assert.equal(
                    config.highlighter_html(testers_item, group_query),
                    $fake_rendered_group,
                );
            }
        })();

        (function test_matcher() {
            let result;
            if (opts.stream) {
                result = config.matcher(denmark_item, stream_query);
                assert.ok(result);
                result = config.matcher(sweden_item, stream_query);
                assert.ok(!result);
            }
            if (opts.user_group && opts.user) {
                /* If user pills are also allowed along with user groups.
                We should check that queries matching either a person
                or group is returned. */

                // group query, with correct item.
                result = config.matcher(testers_item, group_query);
                assert.ok(result);
                // group query, with wrong item.
                result = config.matcher(admins_item, group_query);
                assert.ok(!result);
                // person query with correct item.
                result = config.matcher(me_item, person_query);
                assert.ok(result);
                // person query with wrong item.
                result = config.matcher(jill_item, person_query);
                assert.ok(!result);
            }
            if (opts.user_group && !opts.user) {
                result = config.matcher(testers_item, group_query);
                assert.ok(result);
                result = config.matcher(admins_item, group_query);
                assert.ok(!result);
            }
            if (opts.user && !opts.user_group) {
                result = config.matcher(me_item, person_query);
                assert.ok(result);
                result = config.matcher(jill_item, person_query);
                assert.ok(!result);
            }
        })();

        (function test_sorter() {
            if (opts.stream) {
                sort_streams_called = false;
                config.sorter([denmark_item], stream_query);
                assert.ok(sort_streams_called);
            }
            if (opts.user_group) {
                sort_recipients_called = false;
                config.sorter([testers_item], group_query);
                assert.ok(sort_recipients_called);
            }
            if (opts.user) {
                sort_recipients_called = false;
                config.sorter([me_item], person_query);
                assert.ok(sort_recipients_called);
            }
        })();

        (function test_source() {
            let result;
            if (opts.stream) {
                result = config.source(stream_query);
                const stream_ids = result.map((stream) => stream.stream_id);
                const expected_stream_ids = [denmark.stream_id, sweden.stream_id];
                assert.deepEqual(stream_ids, expected_stream_ids);
            }

            let expected_result = [];
            let actual_result = [];
            function is_group(item) {
                return item.members;
            }
            result = config.source(person_query);
            actual_result = result
                .map((item) => {
                    if (is_group(item)) {
                        return item.id;
                    }
                    return item.user_id;
                })
                .filter(Boolean);
            if (opts.user_group) {
                expected_result = [...expected_result, ...group_items];
            }
            if (opts.user) {
                if (opts.user_source) {
                    expected_result = [...expected_result, ...opts.user_source()];
                } else {
                    expected_result = [...expected_result, ...person_items];
                }
            }
            expected_result = expected_result
                .map((item) => {
                    if (is_group(item)) {
                        return item.id;
                    }
                    return item.user_id;
                })
                .filter(Boolean);
            assert.deepEqual(actual_result, expected_result);
        })();

        (function test_updater() {
            if (opts.user && opts.user_group && opts.stream) {
                // Test it only for the case when all types of pills
                // are allowed, as it would be difficult to keep track
                // of number of items as we call with different types multiple
                // times in this test. So this case checks all possible cases handled by
                // updater in pill_typeahead.

                function number_of_pills() {
                    const pills = $pill_widget.items();
                    return pills.length;
                }
                assert.equal(number_of_pills(), 0);
                config.updater(denmark_item, stream_query);
                assert.equal(number_of_pills(), 1);
                config.updater(me_item, person_query);
                assert.equal(number_of_pills(), 2);
                config.updater(testers_item, group_query);
                assert.equal(number_of_pills(), 3);

                assert.ok(update_func_called);
            }
        })();

        // input_pill_typeahead_called is set true if
        // no exception occurs in pill_typeahead.set_up.
        input_pill_typeahead_called = true;
    });

    function test_pill_typeahead(opts) {
        pill_typeahead.set_up($fake_input, $pill_widget, opts);
        assert.ok(input_pill_typeahead_called);
    }

    const all_possible_opts = [
        // These are various possible cases of opts that
        // currently occur in web-app codebase. This list
        // can be extended if some other configuration
        // is added later and its logic is to be tested.

        {user: true},
        // user and custom user source.
        {user: true, user_source: () => [fred_item, mark_item]},
        {stream: true},
        {user_group: true},
        {user_group: true, stream: true},
        {user_group: true, user: true},
        {user: true, stream: true},
        {user_group: true, stream: true, user: true, update_func},
    ];

    for (const config of all_possible_opts) {
        opts = config;
        test_pill_typeahead(config);
    }

    // Special case to test coverage and to test
    // that we enforce type is always specified
    // by caller.
    opts = {};
    input_pill_typeahead_called = false;
    blueslip.expect("error", "Unspecified possible item types");
    pill_typeahead.set_up($fake_input, $pill_widget, {});
    assert.ok(!input_pill_typeahead_called);
});

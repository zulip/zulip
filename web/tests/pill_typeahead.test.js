"use strict";

const {strict: assert} = require("assert");

const {zrequire, mock_esm} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

const input_pill = zrequire("input_pill");
const pill_typeahead = zrequire("pill_typeahead");
const noop = function () {};

const peer_data = zrequire("peer_data");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const user_groups = zrequire("user_groups");

// set global test variables.
let sort_recipients_called = false;
let sort_streams_called = false;
const $fake_rendered_person = $.create("fake-rendered-person");
const $fake_rendered_stream = $.create("fake-rendered-stream");
const $fake_rendered_group = $.create("fake-rendered-group");

mock_esm("../src/typeahead_helper", {
    render_person() {
        return $fake_rendered_person;
    },
    render_user_group() {
        return $fake_rendered_group;
    },
    render_stream() {
        return $fake_rendered_stream;
    },
    sort_streams() {
        sort_streams_called = true;
    },
    sort_recipients() {
        sort_recipients_called = true;
    },
});

const jill = {
    email: "jill@zulip.com",
    user_id: 10,
    full_name: "Jill Hill",
};
const mark = {
    email: "mark@zulip.com",
    user_id: 20,
    full_name: "Marky Mark",
};
const fred = {
    email: "fred@zulip.com",
    user_id: 30,
    full_name: "Fred Flintstone",
};
const me = {
    email: "me@example.com",
    user_id: 40,
    full_name: "me",
};

const persons = [jill, mark, fred, me];
for (const person of persons) {
    people.add_active_user(person);
}

const admins = {
    name: "Admins",
    description: "foo",
    id: 1,
    members: [jill.user_id, mark.user_id],
};
const testers = {
    name: "Testers",
    description: "bar",
    id: 2,
    members: [mark.user_id, fred.user_id, me.user_id],
};

const groups = [admins, testers];
for (const group of groups) {
    user_groups.add(group);
}

const denmark = {
    stream_id: 1,
    name: "Denmark",
    subscribed: true,
    render_subscribers: true,
};
peer_data.set_subscribers(denmark.stream_id, [me.user_id, mark.user_id]);

const sweden = {
    stream_id: 2,
    name: "Sweden",
    subscribed: false,
};
peer_data.set_subscribers(sweden.stream_id, [mark.user_id, jill.user_id]);

const subs = [denmark, sweden];
for (const sub of subs) {
    stream_data.add_sub(sub);
}

run_test("set_up", ({mock_template}) => {
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

    let opts = {};
    $fake_input.typeahead = (config) => {
        assert.equal(config.items, 5);
        assert.ok(config.fixed);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.highlighter, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // test queries
        const fake_stream_this = {
            query: "#Denmark",
        };
        const fake_person_this = {
            query: "me",
        };
        const fake_group_this = {
            query: "test",
        };

        (function test_highlighter() {
            if (opts.stream) {
                // Test stream highlighter for widgets that allow stream pills.
                assert.equal(
                    config.highlighter.call(fake_stream_this, denmark),
                    $fake_rendered_stream,
                );
            }
            if (opts.user_group && opts.user) {
                // If user is also allowed along with user_group
                // then we should check that each of them rendered correctly.
                assert.equal(
                    config.highlighter.call(fake_group_this, testers),
                    $fake_rendered_group,
                );
                assert.equal(config.highlighter.call(fake_person_this, me), $fake_rendered_person);
            }
            if (opts.user && !opts.user_group) {
                assert.equal(config.highlighter.call(fake_person_this, me), $fake_rendered_person);
            }
            if (!opts.user && opts.user_group) {
                assert.equal(
                    config.highlighter.call(fake_group_this, testers),
                    $fake_rendered_group,
                );
            }
        })();

        (function test_matcher() {
            let result;
            if (opts.stream) {
                result = config.matcher.call(fake_stream_this, denmark);
                assert.ok(result);
                result = config.matcher.call(fake_stream_this, sweden);
                assert.ok(!result);
            }
            if (opts.user_group && opts.user) {
                /* If user pills are also allowed along with user groups.
                We should check that queries matching either a person
                or group is returned. */

                // group query, with correct item.
                result = config.matcher.call(fake_group_this, testers);
                assert.ok(result);
                // group query, with wrong item.
                result = config.matcher.call(fake_group_this, admins);
                assert.ok(!result);
                // person query with correct item.
                result = config.matcher.call(fake_person_this, me);
                assert.ok(result);
                // person query with wrong item.
                result = config.matcher.call(fake_person_this, jill);
                assert.ok(!result);
            }
            if (opts.user_group && !opts.user) {
                result = config.matcher.call(fake_group_this, testers);
                assert.ok(result);
                result = config.matcher.call(fake_group_this, admins);
                assert.ok(!result);
            }
            if (opts.user && !opts.user_group) {
                result = config.matcher.call(fake_person_this, me);
                assert.ok(result);
                result = config.matcher.call(fake_person_this, jill);
                assert.ok(!result);
            }
        })();

        (function test_sorter() {
            if (opts.stream) {
                sort_streams_called = false;
                config.sorter.call(fake_stream_this);
                assert.ok(sort_streams_called);
            }
            if (opts.user_group) {
                sort_recipients_called = false;
                config.sorter.call(fake_group_this, [testers]);
                assert.ok(sort_recipients_called);
            }
            if (opts.user) {
                sort_recipients_called = false;
                config.sorter.call(fake_person_this, [me]);
                assert.ok(sort_recipients_called);
            }
        })();

        (function test_source() {
            let result;
            if (opts.stream) {
                result = config.source.call(fake_stream_this);
                const stream_ids = result.map((stream) => stream.stream_id);
                const expected_stream_ids = [denmark.stream_id, sweden.stream_id];
                assert.deepEqual(stream_ids, expected_stream_ids);
            }

            let expected_result = [];
            let actual_result = [];
            function is_group(item) {
                return item.members;
            }
            result = config.source.call(fake_person_this);
            actual_result = result
                .map((item) => {
                    if (is_group(item)) {
                        return item.id;
                    }
                    return item.user_id;
                })
                .filter(Boolean);
            if (opts.user_group) {
                expected_result = [...expected_result, ...groups];
            }
            if (opts.user) {
                if (opts.user_source) {
                    expected_result = [...expected_result, ...opts.user_source()];
                } else {
                    expected_result = [...expected_result, ...persons];
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
                config.updater.call(fake_stream_this, denmark);
                assert.equal(number_of_pills(), 1);
                config.updater.call(fake_person_this, me);
                assert.equal(number_of_pills(), 2);
                config.updater.call(fake_group_this, testers);
                assert.equal(number_of_pills(), 3);
            }
        })();

        // input_pill_typeahead_called is set true if
        // no exception occurs in pill_typeahead.set_up.
        input_pill_typeahead_called = true;
    };

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
        {user: true, user_source: () => [fred, mark]},
        {stream: true},
        {user_group: true},
        {user_group: true, stream: true},
        {user_group: true, user: true},
        {user: true, stream: true},
        {user_group: true, stream: true, user: true},
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

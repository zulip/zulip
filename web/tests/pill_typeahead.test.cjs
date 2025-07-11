"use strict";

const assert = require("node:assert/strict");

const {zrequire, mock_esm} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const noop = function () {};

const bootstrap_typeahead = mock_esm("../src/bootstrap_typeahead");

const input_pill = zrequire("input_pill");
const pill_typeahead = zrequire("pill_typeahead");
const peer_data = zrequire("peer_data");
const people = zrequire("people");
const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const user_groups = zrequire("user_groups");
const typeahead_helper = zrequire("typeahead_helper");

const current_user = {};
set_current_user(current_user);
const realm = {
    custom_profile_field_types: {
        PRONOUNS: {id: 8},
    },
};
set_realm(realm);

// set global test variables.
let sort_recipients_called = false;
let sort_streams_called = false;
let sort_group_setting_options_called = false;
let sort_stream_or_group_members_options_called = false;
const $fake_rendered_person = $.create("fake-rendered-person");
const $fake_rendered_stream = $.create("fake-rendered-stream");
const $fake_rendered_group = $.create("fake-rendered-group");
const $fake_rendered_topic_state = $.create("fake-rendered-topic-state");

function override_typeahead_helper({mock_template, override_rewire}) {
    mock_template("typeahead_list_item.hbs", false, (args) => {
        if (args.stream) {
            return $fake_rendered_stream;
        } else if (args.is_user_group) {
            return $fake_rendered_group;
        }
        assert.ok(args.is_person);
        return $fake_rendered_person;
    });
    override_rewire(typeahead_helper, "sort_streams", () => {
        sort_streams_called = true;
    });
    override_rewire(typeahead_helper, "sort_stream_or_group_members_options", ({users}) => {
        sort_stream_or_group_members_options_called = true;
        return users;
    });
}

function user_item(user) {
    return {type: "user", user};
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
    members: new Set([jill.user_id, mark.user_id, me.user_id]),
};
const admins_item = user_group_item(admins);
const testers = {
    name: "Testers",
    description: "bar",
    id: 2,
    members: new Set([mark.user_id, fred.user_id, me.user_id]),
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

const sweden = {
    stream_id: 2,
    name: "Sweden",
    subscribed: false,
};
const sweden_item = stream_item(sweden);

const subs = [denmark, sweden];
for (const sub of subs) {
    stream_data.add_sub(sub);
}
peer_data.set_subscribers(denmark.stream_id, [me.user_id, mark.user_id]);
peer_data.set_subscribers(sweden.stream_id, [mark.user_id, jill.user_id]);

run_test("set_up_user", ({mock_template, override, override_rewire}) => {
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.ok(args.is_person);
        return $fake_rendered_person;
    });
    override_rewire(typeahead_helper, "sort_recipients", ({users}) => {
        sort_recipients_called = true;
        return users;
    });
    mock_template("input_pill.hbs", true, (_data, html) => html);
    let input_pill_typeahead_called = false;
    const $fake_input = $.create(".input");
    $fake_input.before = noop;

    const $container = $.create(".pill-container");
    $container.find = () => $fake_input;

    const $pill_widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
        get_display_value_from_item: noop,
    });

    let update_func_called = false;
    function update_func() {
        update_func_called = true;
    }

    override(bootstrap_typeahead, "Typeahead", (input_element, config) => {
        assert.equal(input_element.$element, $fake_input);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.item_html, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // test queries
        const person_query = "me";

        (function test_item_html() {
            assert.equal(config.item_html(me_item, person_query), $fake_rendered_person);
        })();

        (function test_matcher() {
            let result;
            result = config.matcher(me_item, person_query);
            assert.ok(result);
            result = config.matcher(jill_item, person_query);
            assert.ok(!result);
        })();

        (function test_sorter() {
            sort_recipients_called = false;
            config.sorter([me_item], person_query);
            assert.ok(sort_recipients_called);
        })();

        (function test_source() {
            let expected_result = [];
            let actual_result = [];
            const result = config.source(person_query);
            actual_result = result.map((item) => item.user_id);
            expected_result = [...expected_result, ...person_items];
            expected_result = expected_result.map((item) => item.user_id);
            assert.deepEqual(actual_result, expected_result);
        })();

        (function test_updater() {
            function number_of_pills() {
                const pills = $pill_widget.items();
                return pills.length;
            }
            assert.equal(number_of_pills(), 0);
            config.updater(me_item, person_query);
            assert.equal(number_of_pills(), 1);

            assert.ok(update_func_called);
        })();

        // input_pill_typeahead_called is set true if
        // no exception occurs in pill_typeahead.set_up_user.
        input_pill_typeahead_called = true;
    });

    pill_typeahead.set_up_user($fake_input, $pill_widget, {update_func});
    assert.ok(input_pill_typeahead_called);
});

run_test("set_up_stream", ({mock_template, override, override_rewire}) => {
    mock_template("typeahead_list_item.hbs", false, (args) => {
        assert.ok(args.stream !== undefined);
        return $fake_rendered_stream;
    });
    override_rewire(typeahead_helper, "sort_streams_by_name", ({streams}) => {
        sort_streams_called = true;
        return streams;
    });
    mock_template("input_pill.hbs", true, (_data, html) => html);
    let input_pill_typeahead_called = false;
    const $fake_input = $.create(".input");
    $fake_input.before = noop;

    const $container = $.create(".pill-container");
    $container.find = () => $fake_input;

    const $pill_widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
        get_display_value_from_item: noop,
    });

    let update_func_called = false;
    function update_func() {
        update_func_called = true;
    }

    override(bootstrap_typeahead, "Typeahead", (input_element, config) => {
        assert.equal(input_element.$element, $fake_input);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.item_html, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // test queries
        const stream_query = "#denmark";

        (function test_item_html() {
            assert.equal(config.item_html(denmark_item, stream_query), $fake_rendered_stream);
        })();

        (function test_matcher() {
            let result;
            result = config.matcher(denmark_item, stream_query);
            assert.ok(result);
            result = config.matcher(sweden_item, stream_query);
            assert.ok(!result);
        })();

        (function test_sorter() {
            sort_streams_called = false;
            config.sorter([denmark_item], stream_query);
            assert.ok(sort_streams_called);
        })();

        (function test_source() {
            const result = config.source(stream_query);
            const stream_ids = result.map((stream) => stream.stream_id);
            const expected_stream_ids = [denmark.stream_id, sweden.stream_id];
            assert.deepEqual(stream_ids, expected_stream_ids);
        })();

        (function test_updater() {
            function number_of_pills() {
                const pills = $pill_widget.items();
                return pills.length;
            }
            assert.equal(number_of_pills(), 0);
            config.updater(denmark_item, stream_query);
            assert.equal(number_of_pills(), 1);

            assert.ok(update_func_called);
        })();

        // input_pill_typeahead_called is set true if
        // no exception occurs in pill_typeahead.set_up_user.
        input_pill_typeahead_called = true;
    });

    pill_typeahead.set_up_stream($fake_input, $pill_widget, {update_func});
    assert.ok(input_pill_typeahead_called);
});

run_test("set_up_user_group", ({mock_template, override, override_rewire}) => {
    current_user.user_id = me.user_id;
    current_user.full_name = me.full_name;
    current_user.email = me.email;
    let sort_user_groups_called = false;

    override_rewire(typeahead_helper, "render_user_group", () => $fake_rendered_group);
    override_rewire(typeahead_helper, "sort_user_groups", ({user_groups}) => {
        sort_user_groups_called = true;
        return user_groups;
    });

    mock_template("input_pill.hbs", true, (_data, html) => html);

    let input_pill_typeahead_called = false;
    const $fake_input = $.create(".input");
    $fake_input.before = noop;

    const $container = $.create(".pill-container");
    $container.find = () => $fake_input;

    const $pill_widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
        get_display_value_from_item: noop,
    });

    const user_group_source = () => [admins_item, testers_item];

    override(bootstrap_typeahead, "Typeahead", (input_element, config) => {
        current_user.user_id = me.user_id;
        current_user.full_name = me.full_name;
        current_user.email = me.email;
        assert.equal(input_element.$element, $fake_input);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.item_html, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        const group_query = "testers";

        (function test_item_html() {
            assert.equal(config.item_html(testers_item, group_query), $fake_rendered_group);
        })();

        (function test_matcher() {
            let result;
            result = config.matcher(testers_item, group_query);
            assert.ok(result);
            result = config.matcher(admins_item, group_query);
            assert.ok(!result);
        })();

        (function test_sorter() {
            sort_user_groups_called = false;
            config.sorter([testers_item], group_query);
            assert.ok(sort_user_groups_called);
        })();

        (function test_source() {
            const result = config.source(group_query);
            const group_names = result.map((group) => group.name);
            const expected_group_names = ["Admins", "Testers"];
            assert.deepEqual(group_names, expected_group_names);
        })();

        (function test_updater() {
            function number_of_pills() {
                const pills = $pill_widget.items();
                return pills.length;
            }
            assert.equal(number_of_pills(), 0);
            config.updater(testers_item, $fake_rendered_group);
            assert.equal(number_of_pills(), 1);
        })();

        input_pill_typeahead_called = true;
    });

    pill_typeahead.set_up_user_group($fake_input, $pill_widget, {user_group_source});
    assert.ok(input_pill_typeahead_called);
});

run_test("render_topic_state", ({override_rewire}) => {
    override_rewire(typeahead_helper, "render_typeahead_item", (args) => {
        assert.equal(args.primary, "Resolved");
        return $fake_rendered_topic_state;
    });

    const result = typeahead_helper.render_topic_state("Resolved");
    assert.equal(result, $fake_rendered_topic_state);

    override_rewire(typeahead_helper, "render_topic_state", (state) => `${state}`);

    const new_result = typeahead_helper.render_topic_state("Unresolved");
    assert.equal(new_result, "Unresolved");
});

run_test("set_up_combined", ({mock_template, override, override_rewire}) => {
    override_typeahead_helper({mock_template, override_rewire});
    mock_template("input_pill.hbs", true, (_data, html) => html);
    let input_pill_typeahead_called = false;
    const $fake_input = $.create(".input");
    $fake_input.before = noop;

    const $container = $.create(".pill-container");
    $container.find = () => $fake_input;

    const $pill_widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
        get_display_value_from_item: noop,
    });

    let update_func_called = false;
    function update_func() {
        update_func_called = true;
    }

    function mock_pill_removes(widget) {
        const pills = widget._get_pills_for_testing();
        for (const pill of pills) {
            pill.$element.remove = noop;
        }
    }

    let opts = {};
    override(bootstrap_typeahead, "Typeahead", (input_element, config) => {
        assert.equal(input_element.$element, $fake_input);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.item_html, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // test queries
        const stream_query = "#Denmark";
        const person_query = "me";
        const group_query = "test";

        (function test_item_html() {
            if (opts.stream) {
                // Test stream item_html for widgets that allow stream pills.
                assert.equal(config.item_html(denmark_item, stream_query), $fake_rendered_stream);
            }
            if (opts.user_group && opts.user) {
                // If user is also allowed along with user_group
                // then we should check that each of them rendered correctly.
                assert.equal(config.item_html(testers_item, group_query), $fake_rendered_group);
                assert.equal(config.item_html(me_item, person_query), $fake_rendered_person);
            }
            if (opts.user && !opts.user_group) {
                assert.equal(config.item_html(me_item, person_query), $fake_rendered_person);
            }
            if (!opts.user && opts.user_group) {
                assert.equal(config.item_html(testers_item, group_query), $fake_rendered_group);
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
                sort_stream_or_group_members_options_called = false;
                config.sorter([testers_item], group_query);
                assert.ok(!sort_recipients_called);
                assert.ok(sort_stream_or_group_members_options_called);
            }
            if (opts.user) {
                sort_recipients_called = false;
                sort_stream_or_group_members_options_called = false;
                config.sorter([me_item], person_query);
                assert.ok(!sort_recipients_called);
                assert.ok(sort_stream_or_group_members_options_called);
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
                if (opts.user_group_source) {
                    expected_result = [...expected_result, ...opts.user_group_source()];
                } else {
                    expected_result = [...expected_result, ...group_items];
                }
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

                // Clear pills for the next test.
                mock_pill_removes($pill_widget);
                $pill_widget.clear();
            }
        })();

        // input_pill_typeahead_called is set true if
        // no exception occurs in pill_typeahead.set_up_combined.
        input_pill_typeahead_called = true;
    });

    function test_pill_typeahead(opts) {
        pill_typeahead.set_up_combined($fake_input, $pill_widget, opts);
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
        // user and custom user group source.
        {user_group: true, user_group_source: () => [admins_item]},
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
    pill_typeahead.set_up_combined($fake_input, $pill_widget, {});
    assert.ok(!input_pill_typeahead_called);
});

run_test("set_up_group_setting_typeahead", ({mock_template, override, override_rewire}) => {
    mock_template("typeahead_list_item.hbs", false, (args) => {
        if (args.is_user_group) {
            return $fake_rendered_group;
        }
        assert.ok(args.is_person);
        return $fake_rendered_person;
    });
    override_rewire(typeahead_helper, "sort_group_setting_options", () => {
        sort_group_setting_options_called = true;
    });
    mock_template("input_pill.hbs", true, (_data, html) => html);

    let input_pill_typeahead_called = false;
    const $fake_input = $.create(".input");
    $fake_input.before = noop;

    const $container = $.create(".pill-container");
    $container.find = () => $fake_input;

    const $pill_widget = input_pill.create({
        $container,
        create_item_from_text: noop,
        get_text_from_item: noop,
        get_display_value_from_item: noop,
    });

    override(realm, "server_supported_permission_settings", {
        group: {
            can_manage_group: {
                require_system_group: false,
                allow_internet_group: false,
                allow_nobody_group: true,
                allow_everyone_group: false,
                allowed_system_groups: ["role:moderators", "role:nobody", "role:fullmembers"],
            },
        },
    });

    const moderators_system_group = {
        name: "role:moderators",
        id: 3,
        description: "Moderators",
        members: [],
        is_system_group: true,
    };
    const nobody_system_group = {
        name: "role:nobody",
        id: 4,
        description: "Nobody",
        members: [],
        is_system_group: true,
    };
    const full_members_system_group = {
        name: "role:fullmembers",
        id: 5,
        description: "Full members",
        members: [],
        is_system_group: true,
    };
    user_groups.add(moderators_system_group);
    user_groups.add(nobody_system_group);
    user_groups.add(full_members_system_group);

    const moderators_item = user_group_item(moderators_system_group);
    const system_group_items = [moderators_item];

    page_params.development_environment = true;
    override(realm, "realm_waiting_period_threshold", 0);

    override(bootstrap_typeahead, "Typeahead", (input_element, config) => {
        assert.equal(input_element.$element, $fake_input);
        assert.ok(config.dropup);
        assert.ok(config.stopAdvance);

        assert.equal(typeof config.source, "function");
        assert.equal(typeof config.item_html, "function");
        assert.equal(typeof config.matcher, "function");
        assert.equal(typeof config.sorter, "function");
        assert.equal(typeof config.updater, "function");

        // test queries
        const person_query = "me";
        const group_query = "test";

        (function test_item_html() {
            // If user is also allowed along with user_group
            // then we should check that each of them rendered correctly.
            assert.equal(config.item_html(testers_item, group_query), $fake_rendered_group);
            assert.equal(config.item_html(me_item, person_query), $fake_rendered_person);
        })();

        (function test_matcher() {
            let result;
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
        })();

        (function test_sorter() {
            sort_group_setting_options_called = false;
            config.sorter([testers_item], group_query);
            assert.ok(sort_group_setting_options_called);
            sort_group_setting_options_called = false;
            config.sorter([me_item], person_query);
            assert.ok(sort_group_setting_options_called);
        })();

        (function test_source() {
            let expected_result = [];
            let actual_result = [];
            function is_group(item) {
                return item.members;
            }
            const result = config.source(person_query);
            actual_result = result
                .map((item) => {
                    if (is_group(item)) {
                        return item.id;
                    }
                    return item.user_id;
                })
                .filter(Boolean);
            expected_result = [...expected_result, ...system_group_items, ...group_items];
            expected_result = [...expected_result, ...person_items];
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
            function number_of_pills() {
                const pills = $pill_widget.items();
                return pills.length;
            }
            assert.equal(number_of_pills(), 0);
            config.updater(me_item, person_query);
            assert.equal(number_of_pills(), 1);
            config.updater(testers_item, group_query);
            assert.equal(number_of_pills(), 2);
        })();

        input_pill_typeahead_called = true;
    });

    const opts = {
        setting_name: "can_manage_group",
        setting_type: "group",
        group: testers,
    };
    pill_typeahead.set_up_group_setting_typeahead($fake_input, $pill_widget, opts);
    assert.ok(input_pill_typeahead_called);
});

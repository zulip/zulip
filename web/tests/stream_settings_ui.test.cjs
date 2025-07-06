"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

const denmark_stream_id = 101;

const scroll_util = mock_esm("../src/scroll_util", {
    get_content_element: ($element) => $element,
});

mock_esm("../src/hash_util", {
    channel_url_by_user_setting() {},
});

mock_esm("../src/browser_history", {
    update() {},
});

mock_esm("../src/hash_parser", {
    get_current_hash_section: () => denmark_stream_id,
});

mock_esm("../src/group_permission_settings", {
    get_group_permission_setting_config() {
        return {
            allow_everyone_group: false,
        };
    },
});

mock_esm("../src/resize", {
    resize_settings_overlay() {},
});

set_global("page_params", {});

const {set_current_user, set_realm} = zrequire("state_data");
const stream_data = zrequire("stream_data");
const stream_settings_components = zrequire("stream_settings_components");
const stream_settings_ui = zrequire("stream_settings_ui");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);
set_current_user({});
initialize_user_settings({user_settings: {}});

const admins_group = {
    name: "Admins",
    id: 1,
    members: new Set([1]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
const nobody_group = {
    name: "Nobody",
    id: 2,
    members: new Set([]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
const initialize_user_groups = () => {
    user_groups.initialize({realm_user_groups: [admins_group, nobody_group]});
};

run_test("redraw_left_panel", ({override, mock_template}) => {
    initialize_user_groups();
    override(realm, "realm_can_add_subscribers_group", admins_group.id);

    // set-up sub rows stubs
    const denmark = {
        elem: "denmark",
        subscribed: false,
        name: "Denmark",
        stream_id: denmark_stream_id,
        description: "Copenhagen",
        subscribers: [1],
        stream_weekly_traffic: null,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const poland = {
        elem: "poland",
        subscribed: true,
        name: "Poland",
        stream_id: 102,
        description: "monday",
        subscribers: [1, 2, 3],
        stream_weekly_traffic: 13,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const pomona = {
        elem: "pomona",
        subscribed: true,
        name: "Pomona",
        stream_id: 103,
        description: "college",
        subscribers: [],
        stream_weekly_traffic: 0,
        color: "red",
        can_remove_subscribers_group: admins_group.id,
        can_administer_channel_group: nobody_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const cpp = {
        elem: "cpp",
        subscribed: true,
        name: "C++",
        stream_id: 104,
        description: "programming lang",
        subscribers: [1, 2],
        stream_weekly_traffic: 6,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const zzyzx = {
        elem: "zzyzx",
        subscribed: true,
        name: "Zzyzx",
        stream_id: 105,
        description: "california town",
        subscribers: [1, 2],
        stream_weekly_traffic: 6,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const abcd = {
        elem: "abcd",
        subscribed: false,
        name: "Abcd",
        stream_id: 106,
        description: "India town",
        subscribers: [1, 2, 3],
        stream_weekly_traffic: 0,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const utopia = {
        elem: "utopia",
        subscribed: false,
        name: "Utopia",
        stream_id: 107,
        description: "movie",
        subscribers: [1, 2, 3, 4],
        stream_weekly_traffic: 8,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };
    const jerry = {
        elem: "jerry",
        subscribed: false,
        name: "Jerry",
        stream_id: 108,
        description: "cat",
        subscribers: [1],
        stream_weekly_traffic: 4,
        color: "red",
        can_administer_channel_group: nobody_group.id,
        can_remove_subscribers_group: admins_group.id,
        can_add_subscribers_group: admins_group.id,
        can_subscribe_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };

    const sub_row_data = [denmark, poland, pomona, cpp, zzyzx, abcd, utopia, jerry];

    for (const sub of sub_row_data) {
        stream_data.create_sub_from_server_data(sub);
    }

    let populated_subs;

    mock_template("stream_settings/browse_streams_list.hbs", false, (data) => {
        populated_subs = data.subscriptions;
    });

    const filters_dropdown_widget = {
        render: function render() {},
        value: () => "",
    };
    stream_settings_components.set_filters_for_tests(filters_dropdown_widget);

    stream_settings_ui.render_left_panel_superset();

    const sub_stubs = [];

    for (const data of populated_subs) {
        const sub_row = `.stream-row-${CSS.escape(data.elem)}`;
        sub_stubs.push(sub_row);

        $(sub_row).attr("data-stream-id", data.stream_id);
        $(sub_row).detach = () => sub_row;
    }

    $.create("#channels_overlay_container .stream-row", {children: sub_stubs});

    const $no_streams_message = $(".no-streams-to-show");
    const $child_element = $(".subscribed_streams_tab_empty_text");
    $no_streams_message.children = () => $child_element;
    $child_element.hide = () => [];

    let ui_called = false;
    scroll_util.reset_scrollbar = ($elem) => {
        ui_called = true;
        assert.equal($elem, $("#subscription_overlay .streams-list"));
    };

    // Filtering has the side effect of setting the "active" class
    // on our current stream, even if it doesn't match the filter.
    const $denmark_row = $(`.stream-row[data-stream-id='${CSS.escape(denmark_stream_id)}']`);
    // sanity check it's not set to active
    assert.ok(!$denmark_row.hasClass("active"));

    function test_filter(params, expected_streams) {
        $("#channels_overlay_container .stream-row:not(.notdisplayed)").length = 0;
        const stream_ids = stream_settings_ui.redraw_left_panel(params);
        assert.deepEqual(
            stream_ids,
            expected_streams.map((sub) => sub.stream_id),
        );
    }

    // Search with single keyword
    test_filter({input: "Po", show_subscribed: false, show_not_subscribed: false}, [
        poland,
        pomona,
    ]);
    assert.ok(ui_called);

    // The denmark row is active, even though it's not displayed.
    assert.ok($denmark_row.hasClass("active"));

    // Search with multiple keywords
    test_filter({input: "Denmark, Pol", show_subscribed: false, show_not_subscribed: false}, [
        denmark,
        poland,
    ]);
    test_filter({input: "Den, Pol", show_subscribed: false, show_not_subscribed: false}, [
        denmark,
        poland,
    ]);

    // Search is case-insensitive
    test_filter({input: "po", show_subscribed: false, show_not_subscribed: false}, [
        poland,
        pomona,
    ]);

    // Search handles unusual characters like C++
    test_filter({input: "c++", show_subscribed: false, show_not_subscribed: false}, [cpp]);

    // Search subscribed streams only
    test_filter({input: "d", show_subscribed: true, show_not_subscribed: false}, [poland]);

    // Search unsubscribed streams only
    test_filter({input: "d", show_subscribed: false, show_not_subscribed: true}, [abcd, denmark]);

    // Search terms match stream description
    test_filter({input: "Co", show_subscribed: false, show_not_subscribed: false}, [
        denmark,
        pomona,
    ]);

    // Search names AND descriptions
    test_filter({input: "Mon", show_subscribed: false, show_not_subscribed: false}, [
        pomona,
        poland,
    ]);

    // Explicitly order streams by name
    test_filter(
        {
            input: "",
            show_subscribed: false,
            show_not_subscribed: false,
            sort_order: "by-stream-name",
        },
        [abcd, cpp, denmark, jerry, poland, pomona, utopia, zzyzx],
    );

    // Order streams by subscriber count
    test_filter(
        {
            input: "",
            show_subscribed: false,
            show_not_subscribed: false,
            sort_order: "by-subscriber-count",
        },
        [utopia, abcd, poland, cpp, zzyzx, denmark, jerry, pomona],
    );

    // Order streams by weekly traffic
    test_filter(
        {
            input: "",
            show_subscribed: false,
            show_not_subscribed: false,
            sort_order: "by-weekly-traffic",
        },
        [poland, utopia, cpp, zzyzx, jerry, abcd, pomona, denmark],
    );

    // Sort for subscribed only.
    test_filter(
        {
            input: "",
            show_subscribed: true,
            show_not_subscribed: false,
            sort_order: "by-subscriber-count",
        },
        [poland, cpp, zzyzx, pomona],
    );

    // Sort for unsubscribed only.
    test_filter(
        {
            input: "",
            show_subscribed: false,
            show_not_subscribed: true,
            sort_order: "by-subscriber-count",
        },
        [utopia, abcd, denmark, jerry],
    );

    // active stream-row is not included in results
    $(".stream-row-denmark").addClass("active");
    $(".stream-row.active").hasClass = (cls) => {
        assert.equal(cls, "notdisplayed");
        return $(".stream-row-denmark").hasClass("active");
    };
    $(".stream-row.active").removeClass = (cls) => {
        assert.equal(cls, "active");
        $(".stream-row-denmark").removeClass("active");
    };

    test_filter({input: "d", show_subscribed: true}, [poland]);
    assert.ok($(".stream-row-denmark").hasClass("active"));

    $(".stream-row.active").attr("data-stream-id", 101);
    stream_settings_ui.switch_stream_tab("subscribed");
    assert.ok(!$(".stream-row-denmark").hasClass("active"));
    assert.ok(!$(".right .settings").visible());
    assert.ok($(".nothing-selected").visible());
});

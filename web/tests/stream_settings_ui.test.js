"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const denmark_stream_id = 101;

const scroll_util = mock_esm("../src/scroll_util", {
    get_content_element: ($element) => $element,
});

mock_esm("../src/hash_util", {
    by_stream_url() {},
});

mock_esm("../src/browser_history", {
    update() {},
});

mock_esm("../src/hash_parser", {
    get_current_hash_section: () => denmark_stream_id,
});
set_global("page_params", {});

const stream_data = zrequire("stream_data");
const stream_settings_ui = zrequire("stream_settings_ui");
const user_groups = zrequire("user_groups");

run_test("redraw_left_panel", ({mock_template}) => {
    const admins_group = {
        name: "Admins",
        id: 1,
        members: new Set([1]),
        is_system_group: true,
        direct_subgroup_ids: new Set([]),
    };
    user_groups.initialize({realm_user_groups: [admins_group]});

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
        can_remove_subscribers_group: admins_group.id,
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
        can_remove_subscribers_group: admins_group.id,
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
        can_remove_subscribers_group: admins_group.id,
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
        can_remove_subscribers_group: admins_group.id,
        date_created: 1691057093,
        creator_id: null,
    };

    const sub_row_data = [denmark, poland, pomona, cpp, zzyzx];

    for (const sub of sub_row_data) {
        stream_data.create_sub_from_server_data(sub);
    }

    let populated_subs;

    mock_template("stream_settings/browse_streams_list.hbs", false, (data) => {
        populated_subs = data.subscriptions;
    });

    stream_settings_ui.render_left_panel_superset();

    const sub_stubs = [];

    for (const data of populated_subs) {
        const sub_row = `.stream-row-${CSS.escape(data.elem)}`;
        sub_stubs.push(sub_row);

        $(sub_row).attr("data-stream-id", data.stream_id);
        $(sub_row).detach = () => sub_row;
    }

    $.create("#channels_overlay_container .stream-row", {children: sub_stubs});

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
    test_filter({input: "Po", subscribed_only: false}, [poland, pomona]);
    assert.ok(ui_called);

    // The denmark row is active, even though it's not displayed.
    assert.ok($denmark_row.hasClass("active"));

    // Search with multiple keywords
    test_filter({input: "Denmark, Pol", subscribed_only: false}, [denmark, poland]);
    test_filter({input: "Den, Pol", subscribed_only: false}, [denmark, poland]);

    // Search is case-insensitive
    test_filter({input: "po", subscribed_only: false}, [poland, pomona]);

    // Search handles unusual characters like C++
    test_filter({input: "c++", subscribed_only: false}, [cpp]);

    // Search subscribed streams only
    test_filter({input: "d", subscribed_only: true}, [poland]);

    // Search terms match stream description
    test_filter({input: "Co", subscribed_only: false}, [denmark, pomona]);

    // Search names AND descriptions
    test_filter({input: "Mon", subscribed_only: false}, [pomona, poland]);

    // Explicitly order streams by name
    test_filter({input: "", subscribed_only: false, sort_order: "by-stream-name"}, [
        cpp,
        denmark,
        poland,
        pomona,
        zzyzx,
    ]);

    // Order streams by subscriber count
    test_filter({input: "", subscribed_only: false, sort_order: "by-subscriber-count"}, [
        poland,
        cpp,
        zzyzx,
        denmark,
        pomona,
    ]);

    // Order streams by weekly traffic
    test_filter({input: "", subscribed_only: false, sort_order: "by-weekly-traffic"}, [
        poland,
        cpp,
        zzyzx,
        pomona,
        denmark,
    ]);

    // Sort for subscribed only.
    test_filter({input: "", subscribed_only: true, sort_order: "by-subscriber-count"}, [
        poland,
        cpp,
        zzyzx,
        pomona,
    ]);

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

    test_filter({input: "d", subscribed_only: true}, [poland]);
    assert.ok($(".stream-row-denmark").hasClass("active"));

    stream_settings_ui.switch_stream_tab("subscribed");
    assert.ok(!$(".stream-row-denmark").hasClass("active"));
    assert.ok(!$(".right .settings").visible());
    assert.ok($(".nothing-selected").visible());
});

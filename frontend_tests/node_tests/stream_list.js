"use strict";

const {strict: assert} = require("assert");

const {stub_templates} = require("../zjsunit/handlebars");
const {mock_cjs, mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");
const {page_params} = require("../zjsunit/zpage_params");

set_global("document", "document-stub");

page_params.is_admin = false;
page_params.realm_users = [];

const noop = () => {};

mock_cjs("jquery", $);
const narrow_state = mock_esm("../../static/js/narrow_state");
const topic_list = mock_esm("../../static/js/topic_list");
mock_esm("../../static/js/keydown_util", {
    handle: noop,
});
mock_esm("../../static/js/ui", {get_scroll_element: (element) => element});

const {Filter} = zrequire("../js/filter");
const stream_sort = zrequire("stream_sort");
const unread = zrequire("unread");
const stream_active = zrequire("stream_active");
const stream_data = zrequire("stream_data");
const scroll_util = zrequire("scroll_util");
const stream_list = zrequire("stream_list");

const devel = {
    name: "devel",
    stream_id: 100,
    color: "blue",
    subscribed: true,
    pin_to_top: true,
};

const social = {
    name: "social",
    stream_id: 200,
    color: "green",
    subscribed: true,
};

// We use this with override.
let num_unread_for_stream;

function create_devel_sidebar_row() {
    const devel_count = $.create("devel-count");
    const subscription_block = $.create("devel-block");

    const sidebar_row = $("<devel sidebar row>");

    sidebar_row.set_find_results(".subscription_block", subscription_block);
    subscription_block.set_find_results(".unread_count", devel_count);

    stub_templates((template_name, data) => {
        assert.equal(template_name, "stream_sidebar_row");
        assert.equal(data.uri, "#narrow/stream/100-devel");
        return "<devel sidebar row>";
    });

    num_unread_for_stream = 42;
    stream_list.create_sidebar_row(devel);
    assert.equal(devel_count.text(), "42");
}

function create_social_sidebar_row() {
    const social_count = $.create("social-count");
    const subscription_block = $.create("social-block");

    const sidebar_row = $("<social sidebar row>");

    sidebar_row.set_find_results(".subscription_block", subscription_block);
    subscription_block.set_find_results(".unread_count", social_count);

    stub_templates((template_name, data) => {
        assert.equal(template_name, "stream_sidebar_row");
        assert.equal(data.uri, "#narrow/stream/200-social");
        return "<social sidebar row>";
    });

    num_unread_for_stream = 99;
    stream_list.create_sidebar_row(social);
    assert.equal(social_count.text(), "99");
}

function test_ui(label, f) {
    run_test(label, (override) => {
        stream_data.clear_subscriptions();
        stream_list.stream_sidebar.rows.clear();
        f(override);
    });
}

test_ui("create_sidebar_row", (override) => {
    // Make a couple calls to create_sidebar_row() and make sure they
    // generate the right markup as well as play nice with get_stream_li().
    page_params.demote_inactive_streams = 1;
    override(unread, "num_unread_for_stream", () => num_unread_for_stream);

    stream_data.add_sub(devel);
    stream_data.add_sub(social);

    create_devel_sidebar_row();
    create_social_sidebar_row();

    const split = '<hr class="stream-split">';
    const devel_sidebar = $("<devel sidebar row>");
    const social_sidebar = $("<social sidebar row>");

    let appended_elems;
    $("#stream_filters").append = (elems) => {
        appended_elems = elems;
    };

    let topic_list_cleared;
    topic_list.clear = () => {
        topic_list_cleared = true;
    };

    stream_list.build_stream_list();

    assert(topic_list_cleared);

    const expected_elems = [
        devel_sidebar, // pinned
        split, // separator
        social_sidebar, // not pinned
    ];

    assert.deepEqual(appended_elems, expected_elems);

    const social_li = $("<social sidebar row>");
    const stream_id = social.stream_id;

    social_li.length = 0;

    const privacy_elem = $.create("privacy-stub");
    social_li.set_find_results(".stream-privacy", privacy_elem);

    social.invite_only = true;
    social.color = "#222222";
    stub_templates((template_name, data) => {
        assert.equal(template_name, "stream_privacy");
        assert.equal(data.invite_only, true);
        assert.equal(data.dark_background, "dark_background");
        return "<div>privacy-html";
    });
    stream_list.redraw_stream_privacy(social);
    assert.equal(privacy_elem.html(), "<div>privacy-html");

    stream_list.set_in_home_view(stream_id, false);
    assert(social_li.hasClass("out_of_home_view"));

    stream_list.set_in_home_view(stream_id, true);
    assert(!social_li.hasClass("out_of_home_view"));

    const row = stream_list.stream_sidebar.get_row(stream_id);
    override(stream_active, "is_active", () => true);
    row.update_whether_active();
    assert(!social_li.hasClass("inactive_stream"));

    override(stream_active, "is_active", () => false);
    row.update_whether_active();
    assert(social_li.hasClass("inactive_stream"));

    let removed;
    social_li.remove = () => {
        removed = true;
    };

    row.remove();
    assert(removed);
});

test_ui("pinned_streams_never_inactive", (override) => {
    override(unread, "num_unread_for_stream", () => num_unread_for_stream);

    stream_data.add_sub(devel);
    stream_data.add_sub(social);

    create_devel_sidebar_row();
    create_social_sidebar_row();

    // non-pinned streams can be made inactive
    const social_sidebar = $("<social sidebar row>");
    let stream_id = social.stream_id;
    let row = stream_list.stream_sidebar.get_row(stream_id);
    override(stream_active, "is_active", () => false);

    stream_list.build_stream_list();
    assert(social_sidebar.hasClass("inactive_stream"));

    override(stream_active, "is_active", () => true);
    row.update_whether_active();
    assert(!social_sidebar.hasClass("inactive_stream"));

    override(stream_active, "is_active", () => false);
    row.update_whether_active();
    assert(social_sidebar.hasClass("inactive_stream"));

    // pinned streams can never be made inactive
    const devel_sidebar = $("<devel sidebar row>");
    stream_id = devel.stream_id;
    row = stream_list.stream_sidebar.get_row(stream_id);
    override(stream_active, "is_active", () => false);

    stream_list.build_stream_list();
    assert(!devel_sidebar.hasClass("inactive_stream"));

    row.update_whether_active();
    assert(!devel_sidebar.hasClass("inactive_stream"));
});

function add_row(sub) {
    stream_data.add_sub(sub);
    const row = {
        update_whether_active() {},
        get_li() {
            const html = "<" + sub.name + " sidebar row html>";
            const obj = $(html);

            obj.length = 1; // bypass blueslip error

            return obj;
        },
    };
    stream_list.stream_sidebar.set_row(sub.stream_id, row);
}

function initialize_stream_data() {
    // pinned streams
    const develSub = {
        name: "devel",
        stream_id: 1000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    const RomeSub = {
        name: "Rome",
        stream_id: 2000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);

    const testSub = {
        name: "test",
        stream_id: 3000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(testSub);

    // unpinned streams
    const announceSub = {
        name: "announce",
        stream_id: 4000,
        color: "green",
        pin_to_top: false,
        subscribed: true,
    };
    add_row(announceSub);

    const DenmarkSub = {
        name: "Denmark",
        stream_id: 5000,
        color: "green",
        pin_to_top: false,
        subscribed: true,
    };
    add_row(DenmarkSub);

    const carSub = {
        name: "cars",
        stream_id: 6000,
        color: "green",
        pin_to_top: false,
        subscribed: true,
    };
    add_row(carSub);

    stream_list.build_stream_list();
}

function elem($obj) {
    return {to_$: () => $obj};
}

test_ui("zoom_in_and_zoom_out", () => {
    const label1 = $.create("label1 stub");
    const label2 = $.create("label2 stub");

    label1.show();
    label2.show();

    assert(label1.visible());
    assert(label2.visible());

    $.create(".stream-filters-label", {
        children: [elem(label1), elem(label2)],
    });

    const splitter = $.create("hr stub");

    splitter.show();
    assert(splitter.visible());

    $.create(".stream-split", {
        children: [elem(splitter)],
    });

    const stream_li1 = $.create("stream1 stub");
    const stream_li2 = $.create("stream2 stub");

    function make_attr(arg) {
        return (sel) => {
            assert.equal(sel, "data-stream-id");
            return arg;
        };
    }

    stream_li1.attr = make_attr("42");
    stream_li1.hide();
    stream_li2.attr = make_attr("99");

    $.create("#stream_filters li.narrow-filter", {
        children: [elem(stream_li1), elem(stream_li2)],
    });

    $("#stream-filters-container")[0] = {
        dataset: {},
    };
    stream_list.set_event_handlers();

    stream_list.zoom_in_topics({stream_id: 42});

    assert(!label1.visible());
    assert(!label2.visible());
    assert(!splitter.visible());
    assert(stream_li1.visible());
    assert(!stream_li2.visible());
    assert($("#streams_list").hasClass("zoom-in"));

    $("#stream_filters li.narrow-filter").show = () => {
        stream_li1.show();
        stream_li2.show();
    };

    stream_li1.length = 1;
    stream_list.zoom_out_topics({stream_li: stream_li1});

    assert(label1.visible());
    assert(label2.visible());
    assert(splitter.visible());
    assert(stream_li1.visible());
    assert(stream_li2.visible());
    assert($("#streams_list").hasClass("zoom-out"));
});

test_ui("narrowing", (override) => {
    initialize_stream_data();

    topic_list.close = noop;
    topic_list.rebuild = noop;
    topic_list.active_stream_id = noop;
    topic_list.get_stream_li = noop;
    override(scroll_util, "scroll_element_into_container", noop);

    assert(!$("<devel sidebar row html>").hasClass("active-filter"));

    stream_list.set_event_handlers();

    let filter;

    filter = new Filter([{operator: "stream", operand: "devel"}]);
    stream_list.handle_narrow_activated(filter);
    assert($("<devel sidebar row html>").hasClass("active-filter"));

    filter = new Filter([
        {operator: "stream", operand: "cars"},
        {operator: "topic", operand: "sedans"},
    ]);
    stream_list.handle_narrow_activated(filter);
    assert(!$("ul.filters li").hasClass("active-filter"));
    assert(!$("<cars sidebar row html>").hasClass("active-filter")); // false because of topic

    filter = new Filter([{operator: "stream", operand: "cars"}]);
    stream_list.handle_narrow_activated(filter);
    assert(!$("ul.filters li").hasClass("active-filter"));
    assert($("<cars sidebar row html>").hasClass("active-filter"));

    let removed_classes;
    $("ul#stream_filters li").removeClass = (classes) => {
        removed_classes = classes;
    };

    let topics_closed;
    topic_list.close = () => {
        topics_closed = true;
    };

    stream_list.handle_narrow_deactivated();
    assert.equal(removed_classes, "active-filter");
    assert(topics_closed);
});

test_ui("focusout_user_filter", () => {
    stream_list.set_event_handlers();
    const e = {};
    const click_handler = $(".stream-list-filter").get_on_handler("focusout");
    click_handler(e);
});

test_ui("focus_user_filter", (override) => {
    override(scroll_util, "scroll_element_into_container", noop);
    stream_list.set_event_handlers();

    initialize_stream_data();
    stream_list.build_stream_list();

    const e = {
        stopPropagation() {},
    };
    const click_handler = $(".stream-list-filter").get_on_handler("click");
    click_handler(e);
});

test_ui("sort_streams", (override) => {
    override(scroll_util, "scroll_element_into_container", noop);

    // Get coverage on early-exit.
    stream_list.build_stream_list();

    initialize_stream_data();

    override(stream_active, "is_active", (sub) => sub.name !== "cars");

    let appended_elems;
    $("#stream_filters").append = (elems) => {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    const split = '<hr class="stream-split">';
    const expected_elems = [
        $("<devel sidebar row html>"),
        $("<Rome sidebar row html>"),
        $("<test sidebar row html>"),
        split,
        $("<announce sidebar row html>"),
        $("<Denmark sidebar row html>"),
        split,
        $("<cars sidebar row html>"),
    ];

    assert.deepEqual(appended_elems, expected_elems);

    const streams = stream_sort.get_streams();

    assert.deepEqual(streams, [
        // three groups: pinned, normal, dormant
        "devel",
        "Rome",
        "test",
        //
        "announce",
        "Denmark",
        //
        "cars",
    ]);

    const denmark_sub = stream_data.get_sub("Denmark");
    const stream_id = denmark_sub.stream_id;
    assert(stream_list.stream_sidebar.has_row_for(stream_id));
    stream_list.remove_sidebar_row(stream_id);
    assert(!stream_list.stream_sidebar.has_row_for(stream_id));
});

test_ui("separators_only_pinned_and_dormant", (override) => {
    // Test only pinned and dormant streams

    // Get coverage on early-exit.
    stream_list.build_stream_list();

    // pinned streams
    const develSub = {
        name: "devel",
        stream_id: 1000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    const RomeSub = {
        name: "Rome",
        stream_id: 2000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);
    // dormant stream
    const DenmarkSub = {
        name: "Denmark",
        stream_id: 3000,
        color: "blue",
        pin_to_top: false,
        subscribed: true,
    };
    add_row(DenmarkSub);

    override(stream_active, "is_active", (sub) => sub.name !== "Denmark");

    let appended_elems;
    $("#stream_filters").append = (elems) => {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    const split = '<hr class="stream-split">';
    const expected_elems = [
        // pinned
        $("<devel sidebar row html>"),
        $("<Rome sidebar row html>"),
        split,
        // dormant
        $("<Denmark sidebar row html>"),
    ];

    assert.deepEqual(appended_elems, expected_elems);
});

test_ui("separators_only_pinned", () => {
    // Test only pinned streams

    // Get coverage on early-exit.
    stream_list.build_stream_list();

    // pinned streams
    const develSub = {
        name: "devel",
        stream_id: 1000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(develSub);

    const RomeSub = {
        name: "Rome",
        stream_id: 2000,
        color: "blue",
        pin_to_top: true,
        subscribed: true,
    };
    add_row(RomeSub);

    let appended_elems;
    $("#stream_filters").append = (elems) => {
        appended_elems = elems;
    };

    stream_list.build_stream_list();

    const expected_elems = [
        // pinned
        $("<devel sidebar row html>"),
        $("<Rome sidebar row html>"),
        // no separator at the end as no stream follows
    ];

    assert.deepEqual(appended_elems, expected_elems);
});

narrow_state.active = () => false;

test_ui("rename_stream", (override) => {
    initialize_stream_data();

    const sub = stream_data.get_sub_by_name("devel");
    const new_name = "Development";

    stream_data.rename_sub(sub, new_name);

    const li_stub = $.create("li stub");
    li_stub.length = 0;

    stub_templates((name, payload) => {
        assert.equal(name, "stream_sidebar_row");
        assert.deepEqual(payload, {
            name: "Development",
            id: 1000,
            uri: "#narrow/stream/1000-Development",
            is_muted: false,
            invite_only: undefined,
            is_web_public: undefined,
            color: payload.color,
            pin_to_top: true,
            dark_background: payload.dark_background,
        });
        return {to_$: () => li_stub};
    });

    let count_updated;
    override(stream_list, "update_count_in_dom", (li) => {
        assert.equal(li, li_stub);
        count_updated = true;
    });

    stream_list.rename_stream(sub);
    assert(count_updated);
});

test_ui("refresh_pin", (override) => {
    initialize_stream_data();

    override(scroll_util, "scroll_element_into_container", noop);

    const sub = {
        name: "maybe_pin",
        stream_id: 100,
        color: "blue",
        pin_to_top: false,
    };

    stream_data.add_sub(sub);

    const pinned_sub = {
        ...sub,
        pin_to_top: true,
    };

    const li_stub = $.create("li stub");
    li_stub.length = 0;

    stub_templates(() => ({to_$: () => li_stub}));

    override(stream_list, "update_count_in_dom", noop);
    $("#stream_filters").append = noop;

    let scrolled;
    override(stream_list, "scroll_stream_into_view", (li) => {
        assert.equal(li, li_stub);
        scrolled = true;
    });

    stream_list.refresh_pinned_or_unpinned_stream(pinned_sub);
    assert(scrolled);
});

test_ui("create_initial_sidebar_rows", (override) => {
    initialize_stream_data();

    const html_dict = new Map();

    override(stream_list.stream_sidebar, "has_row_for", () => false);
    override(stream_list.stream_sidebar, "set_row", (stream_id, widget) => {
        html_dict.set(stream_id, widget.get_li().html());
    });

    override(stream_list, "update_count_in_dom", noop);

    stub_templates((template_name, data) => {
        assert.equal(template_name, "stream_sidebar_row");
        return "<div>stub-html-" + data.name;
    });

    // Test this code with stubs above...
    stream_list.create_initial_sidebar_rows();

    assert.equal(html_dict.get(1000), "<div>stub-html-devel");
    assert.equal(html_dict.get(5000), "<div>stub-html-Denmark");
});

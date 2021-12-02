"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_esm, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const blueslip = require("../zjsunit/zblueslip");
const $ = require("../zjsunit/zjquery");

const padded_widget = mock_esm("../../static/js/padded_widget");
const message_viewport = mock_esm("../../static/js/message_viewport");

const {localstorage} = zrequire("localstorage");
const people = zrequire("people");
const {BuddyList} = zrequire("buddy_list");
function init_simulated_scrolling() {
    const elem = {
        dataset: {},
        scrollTop: 0,
        scrollHeight: 0,
    };

    $.create("#buddy_list_wrapper", {children: [elem]});

    $("#buddy_list_wrapper_padding").set_height(0);

    return elem;
}
function init_simulated_scrolling_for_sections() {
    const sections = [$("#users"), $("#others")];
    for (const section of sections) {
        section[0] = {
            dataset: {},
            scrollTop: 0,
            scrollHeight: 0,
        };
    }

    const elem = {
        sections,
        dataset: {},
        scrollTop: 0,
        scrollHeight: 0,
    };

    $.create("#buddy_list_wrapper", {children: [elem]});

    $("#buddy_list_wrapper_padding").set_height(0);

    return [sections[0][0], sections[1][0], elem];
}

const alice = {
    email: "alice@zulip.com",
    user_id: 10,
    full_name: "Alice Smith",
};

const bob = {
    email: "bob@zulip.com",
    user_id: 11,
    full_name: "bob Smith",
};
people.add_active_user(bob);

run_test("get_items", () => {
    const buddy_list = new BuddyList();

    // We don't make $alice_li an actual jQuery stub,
    // because our test only cares that it comes
    // back from get_items.
    const $alice_li = "alice stub";
    const sel = "li.user_sidebar_entry";
    const $container = $.create("get_items container", {
        children: [{to_$: () => $alice_li}],
    });
    buddy_list.$container.set_find_results(sel, $container);

    const items = buddy_list.get_items();
    assert.deepEqual(items, [$alice_li]);
});

run_test("basics", ({override, mock_template}) => {
    mock_template("presence_sections.hbs", false, () => "html-stub-from-sections");

    const buddy_list = new BuddyList();
    init_simulated_scrolling();

    override(buddy_list, "get_data_from_keys", () => "data-stub");

    override(buddy_list, "items_to_html", (opts) => {
        assert.equal(opts.items, "data-stub");
        return "html-stub-for-items";
    });

    override(message_viewport, "height", () => 550);
    override(padded_widget, "update_padding", () => {});

    $("#user_presences").append = (html) => {
        assert.equal(html, "html-stub-from-sections");
    };
    $("#users").append = (html) => {
        assert.equal(html, "html-stub-for-items");
    };

    buddy_list.populate({
        user_keys: [alice.user_id, bob.user_id],
        other_keys: [],
    });

    const $alice_li = {length: 1};

    override(buddy_list, "get_li_from_key", (opts) => {
        const key = opts.key;

        assert.equal(key, alice.user_id);
        return $alice_li;
    });

    const $li = buddy_list.find_li({
        key: alice.user_id,
    });
    assert.equal($li, $alice_li);
});

run_test("section_basics", ({override, mock_template}) => {
    mock_template("presence_sections.hbs", false, () => "html-stub-from-template");

    const buddy_list = new BuddyList();
    init_simulated_scrolling_for_sections();

    let get_data_called = false;
    override(buddy_list, "get_data_from_keys", () => {
        get_data_called = true;
        return "data-stub";
    });

    override(buddy_list, "items_to_html", (opts) => {
        assert.equal(opts.items, "data-stub");
        return "html-stub";
    });

    override(message_viewport, "height", () => 550);
    override(padded_widget, "update_padding", () => {});

    $("#user_presences").append = (html) => {
        assert.equal(html, "html-stub-from-template");
    };

    buddy_list.populate({
        user_keys_title: "dummy_user_keys_title",
        user_keys: [alice.user_id],
        other_keys_title: "dummy_other_keys_title",
        other_keys: [bob.user_id],
    });

    // calling render_more when we've already rendered
    // everything should early exit
    get_data_called = false;
    buddy_list.users_render_more({chunk_size: 1});
    assert.equal(get_data_called, false);
    buddy_list.others_render_more({chunk_size: 1});
    assert.equal(get_data_called, false);
});

run_test("big_list", ({mock_template, override}) => {
    mock_template("presence_sections.hbs", false, () => {});

    const buddy_list = new BuddyList();
    const elem = init_simulated_scrolling();

    // Don't actually render, but do simulate filling up
    // the screen.
    let chunks_inserted = 0;

    override(buddy_list, "_render_more", () => {
        elem.scrollHeight += 100;
        chunks_inserted += 1;
    });
    override(message_viewport, "height", () => 550);

    // We will have more than enough users, but still
    // only do 6 chunks of data.
    const num_users = 300;
    const user_ids = [];

    _.times(num_users, (i) => {
        const person = {
            email: "foo" + i + "@zulip.com",
            user_id: 100 + i,
            full_name: "Somebody " + i,
        };
        people.add_active_user(person);
        user_ids.push(person.user_id);
    });

    buddy_list.populate({
        user_keys: user_ids,
        other_keys: [],
    });

    assert.equal(chunks_inserted, 6);
});

run_test("big_list_filled_by_users_section", ({mock_template, override}) => {
    mock_template("presence_sections.hbs", false, () => {});

    const buddy_list = new BuddyList();
    const users_elem = init_simulated_scrolling_for_sections()[0];

    // Don't actually render, but do simulate filling up
    // the screen.
    let user_chunks_inserted = 0;

    override(buddy_list, "users_render_more", () => {
        users_elem.scrollHeight += 100;
        user_chunks_inserted += 1;
    });
    override(message_viewport, "height", () => 550);

    // We will have more than enough users, but still
    // only do 6 chunks of data, which only be users.
    const num_users = 300;
    const user_ids = [];
    const other_ids = [];

    _.times(num_users, (i) => {
        const person = {
            email: "foo" + i + "@zulip.com",
            user_id: 100 + i,
            full_name: "Somebody " + i,
        };
        people.add_active_user(person);
        if (i % 2 === 0) {
            user_ids.push(person.user_id);
        } else {
            other_ids.push(person.user_id);
        }
    });

    buddy_list.populate({
        user_keys_title: "dummy_user_keys_title",
        user_keys: user_ids,
        other_keys_title: "dummy_other_keys_title",
        other_keys: other_ids,
    });

    assert.equal(user_chunks_inserted, 6);
});

run_test("big_list_filled_by_others_section", ({mock_template, override}) => {
    mock_template("presence_sections.hbs", false, () => {});

    const buddy_list = new BuddyList();
    const [users_elem, others_elem, buddy_list_wrapper] = init_simulated_scrolling_for_sections();

    // Don't actually render, but do simulate filling up
    // the screen.
    let user_chunks_inserted = 0;
    let other_chunks_inserted = 0;

    override(buddy_list, "users_render_more", () => {
        users_elem.scrollHeight += 10;
        buddy_list_wrapper.scrollHeight += 10;
        user_chunks_inserted += 1;
        buddy_list.users_render_count += 1;
    });

    override(buddy_list, "others_render_more", () => {
        others_elem.scrollHeight += 100;
        buddy_list_wrapper.scrollHeight += 100;
        other_chunks_inserted += 1;
        buddy_list.others_render_count += 1;
    });
    override(message_viewport, "height", () => 550);

    // We will have more than enough users, but still
    // only do 6 chunks of data, which only be users.
    const num_users = 300;
    const user_ids = [];
    const other_ids = [];

    _.times(num_users, (i) => {
        const person = {
            email: "foo" + i + "@zulip.com",
            user_id: 100 + i,
            full_name: "Somebody " + i,
        };
        people.add_active_user(person);
        if (i % 2 === 0) {
            user_ids.push(person.user_id);
        } else {
            other_ids.push(person.user_id);
        }
    });

    buddy_list.populate({
        user_keys_title: "dummy_user_keys_title",
        user_keys: [101],
        other_keys_title: "dummy_other_keys_title",
        other_keys: other_ids,
    });

    assert.equal(user_chunks_inserted, 1);
    assert.equal(other_chunks_inserted, 6);
});

run_test("update_padding_calls", ({override}) => {
    const buddy_list = new BuddyList();
    const dummy_container_sel = "dummy_container_sel";
    const dummy_padding_sel = "dummy_padding_sel";
    const users_render_count = 2;
    const others_render_count = 4;
    const user_keys = [1, 2, 3, 4, 5];
    const other_keys = [6, 7, 8, 9, 10, 11, 12];
    buddy_list.user_keys = user_keys;
    buddy_list.other_keys = other_keys;
    buddy_list.users_render_count = users_render_count;
    buddy_list.others_render_count = others_render_count;
    buddy_list.container_sel = dummy_container_sel;
    buddy_list.padding_sel = dummy_padding_sel;

    const ls = localstorage();
    function check_rest_params(rest) {
        assert.deepEqual(rest, {
            content_sel: dummy_container_sel,
            padding_sel: dummy_padding_sel,
        });
    }

    ls.set("users_title_collapsed", true);
    ls.set("others_title_collapsed", true);
    override(padded_widget, "update_padding", ({shown_rows, total_rows, ...rest}) => {
        assert.equal(shown_rows, 0);
        assert.equal(total_rows, 0);
        check_rest_params(rest);
    });
    buddy_list.update_padding("not_all_users");

    ls.set("users_title_collapsed", false);
    ls.set("others_title_collapsed", true);
    override(padded_widget, "update_padding", ({shown_rows, total_rows, ...rest}) => {
        assert.equal(shown_rows, users_render_count);
        assert.equal(total_rows, user_keys.length);
        check_rest_params(rest);
    });
    buddy_list.update_padding("not_all_users");

    ls.set("users_title_collapsed", true);
    ls.set("others_title_collapsed", false);
    override(padded_widget, "update_padding", ({shown_rows, total_rows, ...rest}) => {
        assert.equal(shown_rows, others_render_count);
        assert.equal(total_rows, other_keys.length);
        check_rest_params(rest);
    });
    buddy_list.update_padding("not_all_users");

    ls.set("users_title_collapsed", false);
    ls.set("others_title_collapsed", false);
    override(padded_widget, "update_padding", ({shown_rows, total_rows, ...rest}) => {
        assert.equal(shown_rows, users_render_count + others_render_count);
        assert.equal(total_rows, user_keys.length + other_keys.length);
        check_rest_params(rest);
    });
    buddy_list.update_padding("not_all_users");
});

run_test("force_render", ({override}) => {
    const buddy_list = new BuddyList();
    buddy_list.users_render_count = 50;

    let num_rendered = 0;
    override(buddy_list, "_render_more", (opts) => {
        num_rendered += opts.chunk_size;
    });

    buddy_list.force_render_users({
        pos: 60,
    });

    assert.equal(num_rendered, 60 - 50 + 3);

    // Force a contrived error case for line coverage.
    blueslip.expect("error", "cannot show key at this position: 10");
    buddy_list.force_render_users({
        pos: 10,
    });

    blueslip.reset();

    buddy_list.others_render_count = 50;
    num_rendered = 0;
    override(buddy_list, "others_render_more", (opts) => {
        num_rendered += opts.chunk_size;
    });

    buddy_list.force_render_others({
        pos: 60,
    });

    assert.equal(num_rendered, 60 - 50 + 3);

    // // Force a contrived error case for line coverage.
    blueslip.expect("error", "cannot show key at this position: 10");
    buddy_list.force_render_others({
        pos: 10,
    });
});

run_test("find_li w/force_render", ({override}) => {
    const buddy_list = new BuddyList();

    // If we call find_li w/force_render set, and the
    // key is not already rendered in DOM, then the
    // widget will call show_key to force-render it
    // (this test achieves the above by simply setting
    // the "..._keys" arrays without using "populate".).
    const user_key = "999";
    const $stub_li = {length: 0};

    override(buddy_list, "get_li_from_key", (opts) => {
        assert.equal(opts.key, user_key);
        return $stub_li;
    });

    buddy_list.user_keys = ["foo", "bar", user_key, "baz"];

    let user_shown;
    override(buddy_list, "force_render_users", (opts) => {
        assert.equal(opts.pos, 2);
        user_shown = true;
    });

    const empty_user_row = buddy_list.find_li({
        key: user_key,
    });
    assert.equal(empty_user_row, $stub_li);
    assert.ok(!user_shown);

    const user_row = buddy_list.find_li({
        key: user_key,
        force_render: true,
    });

    assert.equal(user_row, $stub_li);
    assert.ok(user_shown);

    const other_key = "900";

    override(buddy_list, "get_li_from_key", (opts) => {
        assert.equal(opts.key, other_key);
        return $stub_li;
    });

    buddy_list.other_keys = ["qux", "quux", other_key, "corge"];

    let other_shown;
    override(buddy_list, "force_render_others", (opts) => {
        assert.equal(opts.pos, 2);
        other_shown = true;
    });

    const $empty_li = buddy_list.find_li({
        key: other_key,
    });
    assert.equal($empty_li, $stub_li);
    assert.ok(!other_shown);

    const $li = buddy_list.find_li({
        key: other_key,
        force_render: true,
    });

    assert.equal($li, $stub_li);
    assert.ok(other_shown);
});

run_test("find_li w/bad key", ({override}) => {
    const buddy_list = new BuddyList();
    override(buddy_list, "get_li_from_key", () => ({length: 0}));

    const $undefined_li = buddy_list.find_li({
        key: "not-there",
        force_render: true,
    });

    assert.deepEqual($undefined_li, []);
});

run_test("sections_collapsable", ({mock_template, override}) => {
    // persistence
    people.add_active_user(alice);
    const buddy_list = new BuddyList();
    let fill_screen_called;
    override(buddy_list, "fill_screen_with_content", () => {
        fill_screen_called = true;
    });
    mock_template("presence_sections.hbs", false, (args) => {
        assert.equal(args.users_title_collapsed, false);
        assert.equal(args.others_title_collapsed, false);
    });
    buddy_list.populate({
        user_keys: [alice.user_id],
        other_keys: [bob.user_id],
    });
    $("#users").get_on_handler("hide")();
    $("#others").get_on_handler("hide")();
    mock_template("presence_sections.hbs", false, (args) => {
        assert.equal(args.users_title_collapsed, true);
        assert.equal(args.others_title_collapsed, true);
    });
    buddy_list.populate({
        user_keys: [alice.user_id],
        other_keys: [bob.user_id],
    });

    $("#users").get_on_handler("show")();
    $("#others").get_on_handler("show")();
    mock_template("presence_sections.hbs", false, (args) => {
        assert.equal(args.users_title_collapsed, false);
        assert.equal(args.others_title_collapsed, false);
    });
    buddy_list.populate({
        user_keys: [alice.user_id],
        other_keys: [bob.user_id],
    });

    let update_padding_called = false;
    override(padded_widget, "update_padding", () => {
        update_padding_called = true;
    });

    function reset_called_flags() {
        update_padding_called = false;
        fill_screen_called = false;
    }

    function assert_calls() {
        assert.ok(update_padding_called);
        assert.ok(fill_screen_called);
    }

    reset_called_flags();
    $("#users").get_on_handler("shown")();
    assert_calls();

    reset_called_flags();
    $("#others").get_on_handler("shown")();
    assert_calls();

    reset_called_flags();
    $("#users").get_on_handler("hidden")();
    assert_calls();

    reset_called_flags();
    $("#others").get_on_handler("hidden")();
    assert.ok(update_padding_called);
    assert.ok(!fill_screen_called);
});

run_test("minimum_render_in_sections", ({mock_template, override}) => {
    const buddy_list = new BuddyList();
    init_simulated_scrolling_for_sections();
    override(message_viewport, "height", () => 550);
    const ls = localstorage();
    ls.set("users_title_collapsed", true);
    ls.set("others_title_collapsed", true);
    override(buddy_list, "users_render_more", () => {
        buddy_list.users_render_count += 1;
    });

    override(buddy_list, "others_render_more", () => {
        buddy_list.others_render_count += 1;
    });

    mock_template("presence_sections.hbs", false, (args) => {
        assert.equal(args.users_title_collapsed, true);
        assert.equal(args.others_title_collapsed, true);
    });

    buddy_list.populate({
        user_keys_title: "dummy_user_keys_title",
        user_keys: [alice.user_id],
        other_keys_title: "dummy_other_keys_title",
        other_keys: [bob.user_id],
    });

    assert.equal(buddy_list.users_render_count, 1);
    assert.equal(buddy_list.others_render_count, 1);
});

run_test("scrolling", ({mock_template, override}) => {
    mock_template("presence_sections.hbs", false, () => {});
    const buddy_list = new BuddyList();
    init_simulated_scrolling();

    override(message_viewport, "height", () => 550);

    buddy_list.populate({
        user_keys: [],
        other_keys: [],
    });

    let tried_to_fill;

    override(buddy_list, "fill_screen_with_content", () => {
        tried_to_fill = true;
    });

    assert.ok(!tried_to_fill);

    buddy_list.start_scroll_handler();
    $(buddy_list.scroll_container_sel).trigger("scroll");

    assert.ok(tried_to_fill);
});

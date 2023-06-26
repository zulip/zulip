"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");

const padded_widget = mock_esm("../src/padded_widget");
const message_viewport = mock_esm("../src/message_viewport");

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

const alice = {
    email: "alice@zulip.com",
    user_id: 10,
    full_name: "Alice Smith",
};
people.add_active_user(alice);

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

run_test("basics", ({override}) => {
    const buddy_list = new BuddyList();
    init_simulated_scrolling();

    override(buddy_list, "get_data_from_keys", (opts) => {
        const keys = opts.keys;
        assert.deepEqual(keys, [alice.user_id]);
        return "data-stub";
    });

    override(buddy_list, "items_to_html", (opts) => {
        const items = opts.items;
        assert.equal(items, "data-stub");
        return "html-stub";
    });

    override(message_viewport, "height", () => 550);
    override(padded_widget, "update_padding", () => {});

    let appended;
    $("#user_presences").append = (html) => {
        assert.equal(html, "html-stub");
        appended = true;
    };

    buddy_list.populate({
        keys: [alice.user_id],
    });
    assert.ok(appended);

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

run_test("big_list", ({override}) => {
    const buddy_list = new BuddyList();
    const elem = init_simulated_scrolling();

    // Don't actually render, but do simulate filling up
    // the screen.
    let chunks_inserted = 0;

    override(buddy_list, "render_more", () => {
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
        keys: user_ids,
    });

    assert.equal(chunks_inserted, 6);
});

run_test("force_render", ({override}) => {
    const buddy_list = new BuddyList();
    buddy_list.render_count = 50;

    let num_rendered = 0;
    override(buddy_list, "render_more", (opts) => {
        num_rendered += opts.chunk_size;
    });

    buddy_list.force_render({
        pos: 60,
    });

    assert.equal(num_rendered, 60 - 50 + 3);

    // Force a contrived error case for line coverage.
    blueslip.expect("error", "cannot show key at this position");
    buddy_list.force_render({
        pos: 10,
    });
});

run_test("find_li w/force_render", ({override}) => {
    const buddy_list = new BuddyList();

    // If we call find_li w/force_render set, and the
    // key is not already rendered in DOM, then the
    // widget will call show_key to force-render it.
    const key = "999";
    const $stub_li = {length: 0};

    override(buddy_list, "get_li_from_key", (opts) => {
        assert.equal(opts.key, key);
        return $stub_li;
    });

    buddy_list.keys = ["foo", "bar", key, "baz"];

    let shown;

    override(buddy_list, "force_render", (opts) => {
        assert.equal(opts.pos, 2);
        shown = true;
    });

    const $empty_li = buddy_list.find_li({
        key,
    });
    assert.equal($empty_li, $stub_li);
    assert.ok(!shown);

    const $li = buddy_list.find_li({
        key,
        force_render: true,
    });

    assert.equal($li, $stub_li);
    assert.ok(shown);
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

run_test("scrolling", ({override}) => {
    const buddy_list = new BuddyList();
    init_simulated_scrolling();

    override(message_viewport, "height", () => 550);

    buddy_list.populate({
        keys: [],
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

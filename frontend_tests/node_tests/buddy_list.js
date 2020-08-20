"use strict";

const _ = require("lodash");

set_global("$", global.make_zjquery());
const people = zrequire("people");
zrequire("buddy_data");
zrequire("buddy_list");
zrequire("ui");

set_global("padded_widget", {
    update_padding: () => {},
});

function init_simulated_scrolling() {
    set_global("message_viewport", {
        height: () => 550,
    });

    const elem = {
        dataset: {},
        scrollTop: 0,
        scrollHeight: 0,
    };

    $("#buddy_list_wrapper")[0] = elem;

    $("#buddy_list_wrapper_padding").height = () => 0;

    return elem;
}

const alice = {
    email: "alice@zulip.com",
    user_id: 10,
    full_name: "Alice Smith",
};
people.add_active_user(alice);

run_test("get_items", () => {
    const alice_li = $.create("alice stub");
    const sel = "li.user_sidebar_entry";

    buddy_list.container.set_find_results(sel, {
        map: (f) => [f(0, alice_li)],
    });
    const items = buddy_list.get_items();

    assert.deepEqual(items, [alice_li]);
});

run_test("basics", () => {
    init_simulated_scrolling();

    buddy_list.get_data_from_keys = (opts) => {
        const keys = opts.keys;
        assert.deepEqual(keys, [alice.user_id]);
        return "data-stub";
    };

    buddy_list.items_to_html = (opts) => {
        const items = opts.items;

        assert.equal(items, "data-stub");

        return "html-stub";
    };

    let appended;
    buddy_list.container.append = (html) => {
        assert.equal(html, "html-stub");
        appended = true;
    };

    buddy_list.populate({
        keys: [alice.user_id],
    });
    assert(appended);

    const alice_li = $.create("alice-li-stub");
    alice_li.length = 1;

    buddy_list.get_li_from_key = (opts) => {
        const key = opts.key;

        assert.equal(key, alice.user_id);
        return alice_li;
    };

    const li = buddy_list.find_li({
        key: alice.user_id,
    });
    assert.equal(li, alice_li);
});

run_test("big_list", () => {
    const elem = init_simulated_scrolling();

    // Don't actually render, but do simulate filling up
    // the screen.
    let chunks_inserted = 0;

    buddy_list.render_more = () => {
        elem.scrollHeight += 100;
        chunks_inserted += 1;
    };

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

run_test("force_render", () => {
    buddy_list.render_count = 50;

    let num_rendered = 0;
    buddy_list.render_more = (opts) => {
        num_rendered += opts.chunk_size;
    };

    buddy_list.force_render({
        pos: 60,
    });

    assert.equal(num_rendered, 60 - 50 + 3);

    // Force a contrived error case for line coverage.
    blueslip.expect("error", "cannot show key at this position: 10");
    buddy_list.force_render({
        pos: 10,
    });
});

run_test("find_li w/force_render", () => {
    // If we call find_li w/force_render set, and the
    // key is not already rendered in DOM, then the
    // widget will call show_key to force-render it.
    const key = "999";
    const stub_li = $.create("nada");

    stub_li.length = 0;

    buddy_list.get_li_from_key = (opts) => {
        assert.equal(opts.key, key);
        return stub_li;
    };

    buddy_list.keys = ["foo", "bar", key, "baz"];

    let shown;

    buddy_list.force_render = (opts) => {
        assert.equal(opts.pos, 2);
        shown = true;
    };

    const empty_li = buddy_list.find_li({
        key,
    });
    assert.equal(empty_li, stub_li);
    assert(!shown);

    const li = buddy_list.find_li({
        key,
        force_render: true,
    });

    assert.equal(li, stub_li);
    assert(shown);

    buddy_list.get_li_from_key = () => ({length: 0});

    const undefined_li = buddy_list.find_li({
        key: "not-there",
        force_render: true,
    });

    // very hacky:
    assert.equal(undefined_li.length, 0);
});

run_test("scrolling", () => {
    buddy_list.populate({
        keys: [],
    });

    let tried_to_fill;

    buddy_list.fill_screen_with_content = () => {
        tried_to_fill = true;
    };

    assert(!tried_to_fill);

    buddy_list.start_scroll_handler();
    $(buddy_list.scroll_container_sel).trigger("scroll");

    assert(tried_to_fill);
});

// You have to be careful here about where you place tests,
// since there is lots of stubbing in this module.

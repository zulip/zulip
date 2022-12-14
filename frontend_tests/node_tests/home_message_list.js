"use strict";

const {strict: assert} = require("assert");

const {mock_esm, set_global, zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");
const $ = require("../zjsunit/zjquery");

// Stub out some functions, similar to tests for message_list

const noop = function () {};

set_global("document", {
    to_$() {
        return {
            trigger() {},
        };
    },
});

const {HomeMessageList} = zrequire("home_message_list");

function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
        clear_rendering_state: noop,
    };
}
mock_esm("../../static/js/message_list_view", {
    MessageListView,
});
const {Filter} = zrequire("filter");

// Need to stub this out or show_empty_narrow_message will not work;
// for testing home_message_list it only matters that the banner
// is set with any HTML.
function narrow_error() {
    return "<div></div>";
}

mock_esm("../../static/js/narrow_error", {
    narrow_error,
});

run_test("basics", () => {
    const filter = new Filter();

    const home_list = new HomeMessageList({
        filter,
    });
    // test that new attributes assigned correctly after initialization
    assert.equal(home_list.current, true);
    assert.equal(home_list.table_name, "zhome");
    assert.equal(home_list.empty(), true);

    // add some messages and make sure basic functionality works
    const messages = [{id: 30}, {id: 40}, {id: 50, content: "fifty"}, {id: 60}];
    home_list.append(messages, true);
    assert.equal(home_list.num_items(), 4);
    assert.equal(home_list.empty(), false);
    assert.equal(home_list.get(50).content, "fifty");
    assert.deepEqual(home_list.all_messages(), messages);

    home_list.clear();
    assert.deepEqual(home_list.all_messages(), []);
});

run_test("set_current_message_list", () => {
    const filter = new Filter();

    const home_list = new HomeMessageList({
        filter,
    });
    // test that setter works
    assert.equal(home_list.current, true);
    home_list.set_current_message_list(false);
    assert.equal(home_list.current, false);
});

run_test("handle_empty_narrow_banner", () => {
    const filter = new Filter();
    $(".empty_feed_notice_main");
    const home_list = new HomeMessageList({
        filter,
    });
    assert.equal(home_list.current, true);
    assert.equal(home_list.empty(), true);
    // banner shouldn't be showing
    assert.equal($(".empty_feed_notice_main").html(), "never-been-set");

    home_list.handle_empty_narrow_banner();

    // banner should now be showing
    assert.notEqual($(".empty_feed_notice_main").html(), "");

    // shouldn't have banner when it isn't empty
    const messages = [{id: 30}, {id: 40}, {id: 50, content: "fifty"}, {id: 60}];
    home_list.append(messages, true);
    home_list.handle_empty_narrow_banner();
    assert.equal($(".empty_feed_notice_main").html(), "");

    // Navigate away and clear messages
    home_list.clear();
    home_list.set_current_message_list(false);

    // We won't add banner when we aren't on the current page
    home_list.handle_empty_narrow_banner();
    assert.equal($(".empty_feed_notice_main").html(), "");
});

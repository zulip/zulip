"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const message_lists = mock_esm("../src/message_lists", {
    current: undefined,
});
const message_view = mock_esm("../src/message_view", {
    fast_track_current_msg_list_to_anchor() {},
});
const message_viewport = mock_esm("../src/message_viewport", {
    at_rendered_bottom() {
        return false;
    },
    at_rendered_top() {
        return false;
    },
    height() {
        return 1000;
    },
    message_viewport_info() {
        return {
            visible_top: 0,
            visible_bottom: 300,
            visible_height: 300,
        };
    },
    scrollTop() {},
    set_last_movement_direction() {},
});
const unread_ops = mock_esm("../src/unread_ops", {
    process_visible() {},
});
const user_settings = {
    web_smooth_topic_navigation: false,
};
mock_esm("../src/user_settings", {user_settings});

const navigate = zrequire("navigate");

function make_row(props) {
    return {
        length: 1,
        get_offset_to_window() {
            return props;
        },
    };
}

run_test("down default behavior selects next message", () => {
    let select_args;
    message_lists.current = {
        get_row() {
            return make_row({top: 20, bottom: 80, height: 60});
        },
        is_at_end() {
            return false;
        },
        next() {
            return 101;
        },
        select_id(id, opts) {
            select_args = {id, opts};
        },
        selected_row() {
            return make_row({top: 20, bottom: 80, height: 60});
        },
    };

    navigate.down();

    assert.deepEqual(select_args, {
        id: 101,
        opts: {then_scroll: true, from_scroll: true},
    });
});

run_test("down smooth behavior still selects fully visible next message", () => {
    user_settings.web_smooth_topic_navigation = true;
    let select_args;
    let scroll_top_called = false;
    message_viewport.scrollTop = () => {
        scroll_top_called = true;
    };

    message_lists.current = {
        get_row() {
            return make_row({top: 120, bottom: 180, height: 60});
        },
        is_at_end() {
            return false;
        },
        next() {
            return 102;
        },
        select_id(id, opts) {
            select_args = {id, opts};
        },
        selected_row() {
            return make_row({top: 40, bottom: 100, height: 60});
        },
    };

    navigate.down();

    assert.deepEqual(select_args, {
        id: 102,
        opts: {then_scroll: true, from_scroll: true},
    });
    assert.equal(scroll_top_called, false);
    user_settings.web_smooth_topic_navigation = false;
});

run_test("down smooth behavior scrolls at viewport edge", () => {
    user_settings.web_smooth_topic_navigation = true;
    let target_scroll_top;
    let select_called = false;
    message_viewport.scrollTop = (value) => {
        if (value === undefined) {
            return 100;
        }
        target_scroll_top = value;
    };

    message_lists.current = {
        get_row() {
            return make_row({top: 260, bottom: 340, height: 80});
        },
        is_at_end() {
            return false;
        },
        next() {
            return 103;
        },
        select_id() {
            select_called = true;
        },
        selected_row() {
            return make_row({top: 180, bottom: 240, height: 60});
        },
    };

    navigate.down();

    assert.equal(target_scroll_top, 140);
    assert.equal(select_called, false);
    user_settings.web_smooth_topic_navigation = false;
});

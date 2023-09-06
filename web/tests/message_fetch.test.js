"use strict";

const {strict: assert} = require("assert");

const _ = require("lodash");

const {mock_esm, set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

set_global("document", "document-stub");

const noop = () => {};

function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});

mock_esm("../src/recent_view_ui", {
    process_messages: noop,
    show_loading_indicator: noop,
    hide_loading_indicator: noop,
});
mock_esm("../src/ui_report", {
    hide_error: noop,
});

const channel = mock_esm("../src/channel");
const message_helper = mock_esm("../src/message_helper");
const message_lists = mock_esm("../src/message_lists");
const message_util = mock_esm("../src/message_util");
const stream_list = mock_esm("../src/stream_list", {
    maybe_scroll_narrow_into_view() {},
});
mock_esm("../src/message_feed_top_notices", {
    update_top_of_narrow_notices() {},
});
mock_esm("../src/message_feed_loading", {
    show_loading_older: noop,
    hide_loading_older: noop,
    show_loading_newer: noop,
    hide_loading_newer: noop,
});
set_global("document", "document-stub");

const message_fetch = zrequire("message_fetch");

const {all_messages_data} = zrequire("all_messages_data");
const {Filter} = zrequire("../src/filter");
const message_list = zrequire("message_list");
const people = zrequire("people");

const alice = {
    email: "alice@example.com",
    user_id: 7,
    full_name: "Alice",
};
people.add_active_user(alice);

function make_home_msg_list() {
    const table_name = "whatever";
    const filter = new Filter();

    const list = new message_list.MessageList({
        table_name,
        filter,
    });
    return list;
}

function reset_lists() {
    message_lists.home = make_home_msg_list();
    message_lists.current = message_lists.home;
    all_messages_data.clear();
}

function config_fake_channel(conf) {
    const self = {};
    let called;
    let called_with_newest_flag = false;

    channel.get = (opts) => {
        assert.equal(opts.url, "/json/messages");
        // There's a separate call with anchor="newest" that happens
        // unconditionally; do basic verification of that call.
        if (opts.data.anchor === "newest") {
            assert.ok(!called_with_newest_flag, "Only one 'newest' call allowed");
            called_with_newest_flag = true;
            assert.equal(opts.data.num_after, 0);
            return;
        }

        assert.ok(!called || conf.can_call_again, "only use this for one call");
        if (!conf.can_call_again) {
            assert.equal(self.success, undefined);
        }
        assert.deepEqual(opts.data, conf.expected_opts_data);
        self.success = opts.success;
        called = true;
    };

    return self;
}

function config_process_results(messages) {
    const self = {};

    const messages_processed_for_new = [];

    message_helper.process_new_message = (message) => {
        messages_processed_for_new.push(message);
        return message;
    };

    message_util.do_unread_count_updates = (arg) => {
        assert.deepEqual(arg, messages);
    };

    message_util.add_old_messages = (new_messages, msg_list) => {
        assert.deepEqual(new_messages, messages);
        msg_list.add_messages(new_messages);
    };

    stream_list.update_streams_sidebar = noop;

    self.verify = () => {
        assert.deepEqual(messages_processed_for_new, messages);
    };

    return self;
}

function message_range(start, end) {
    return _.range(start, end).map((idx) => ({
        id: idx,
    }));
}

const initialize_data = {
    initial_fetch: {
        req: {
            anchor: "first_unread",
            num_before: 200,
            num_after: 200,
            client_gravatar: true,
        },
        resp: {
            messages: message_range(201, 801),
            found_newest: false,
            anchor: 444,
        },
    },

    forward_fill: {
        req: {
            anchor: "800",
            num_before: 0,
            num_after: 1000,
            client_gravatar: true,
        },
        resp: {
            messages: message_range(800, 1000),
            found_newest: true,
        },
    },

    back_fill: {
        req: {
            anchor: "201",
            num_before: 1000,
            num_after: 0,
            client_gravatar: true,
        },
        resp: {
            messages: message_range(100, 200),
            found_oldest: true,
        },
    },
};

function test_fetch_success(opts) {
    const response = opts.response;
    const messages = response.messages;

    const process_results = config_process_results(messages);
    opts.fetch.success(response);
    process_results.verify();
}

function initial_fetch_step(home_view_loaded) {
    const self = {};

    let fetch;
    const response = initialize_data.initial_fetch.resp;

    self.prep = () => {
        fetch = config_fake_channel({
            expected_opts_data: initialize_data.initial_fetch.req,
        });

        message_fetch.initialize(home_view_loaded);
    };

    self.finish = () => {
        test_fetch_success({
            fetch,
            response,
        });
    };

    return self;
}

function forward_fill_step() {
    const self = {};

    let fetch;

    self.prep = () => {
        fetch = config_fake_channel({
            expected_opts_data: initialize_data.forward_fill.req,
        });
    };

    self.finish = () => {
        const response = initialize_data.forward_fill.resp;

        let idle_config;
        $("document-stub").idle = (config) => {
            idle_config = config;
        };

        test_fetch_success({
            fetch,
            response,
        });

        assert.equal(idle_config.idle, 10000);

        return idle_config;
    };

    return self;
}

function test_backfill_idle(idle_config) {
    const fetch = config_fake_channel({
        expected_opts_data: initialize_data.back_fill.req,
    });

    const response = initialize_data.back_fill.resp;

    idle_config.onIdle();

    test_fetch_success({
        fetch,
        response,
    });
}

run_test("initialize", () => {
    reset_lists();

    let home_loaded = false;
    page_params.unread_msgs = {
        old_unreads_missing: false,
    };

    function home_view_loaded() {
        home_loaded = true;
    }

    const step1 = initial_fetch_step(home_view_loaded);

    step1.prep();

    const step2 = forward_fill_step();

    step2.prep();
    step1.finish();

    assert.ok(!home_loaded);
    const idle_config = step2.finish();
    assert.ok(home_loaded);

    test_backfill_idle(idle_config);
});

function simulate_narrow() {
    const filter = new Filter([{operator: "dm", operand: alice.email}]);

    const msg_list = new message_list.MessageList({
        table_name: "zfilt",
        filter,
    });
    message_lists.current = msg_list;

    return msg_list;
}

run_test("loading_newer", () => {
    function test_dup_new_fetch(msg_list) {
        assert.equal(msg_list.data.fetch_status.can_load_newer_messages(), false);
        message_fetch.maybe_load_newer_messages({
            msg_list,
        });
    }

    function test_happy_path(opts) {
        const msg_list = opts.msg_list;
        const data = opts.data;

        const fetch = config_fake_channel({
            expected_opts_data: data.req,
            can_call_again: true,
        });

        // The msg_list is empty and we are calling frontfill, which should
        // raise fatal error.
        if (opts.empty_msg_list) {
            assert.throws(
                () => {
                    message_fetch.maybe_load_newer_messages({
                        msg_list,
                        show_loading: noop,
                        hide_loading: noop,
                    });
                },
                {
                    name: "Error",
                    message: "There are no message available to frontfill.",
                },
            );
        } else {
            message_fetch.maybe_load_newer_messages({
                msg_list,
                show_loading: noop,
                hide_loading: noop,
            });

            test_dup_new_fetch(msg_list);

            test_fetch_success({
                fetch,
                response: data.resp,
            });
        }
    }

    (function test_narrow() {
        const msg_list = simulate_narrow();
        page_params.unread_msgs = {
            old_unreads_missing: true,
        };

        const data = {
            req: {
                anchor: "444",
                num_before: 0,
                num_after: 100,
                narrow: `[{"negated":false,"operator":"dm","operand":[${alice.user_id}]}]`,
                client_gravatar: true,
            },
            resp: {
                messages: message_range(500, 600),
                found_newest: false,
            },
        };

        test_happy_path({
            msg_list,
            data,
            empty_msg_list: true,
        });

        msg_list.append_to_view = () => {};
        // Instead of using 444 as page_param.pointer, we
        // should have a message with that id in the message_list.
        msg_list.append(message_range(444, 445), false);

        test_happy_path({
            msg_list,
            data,
            empty_msg_list: false,
        });

        assert.equal(msg_list.data.fetch_status.can_load_newer_messages(), true);

        // The server successfully responded with messages having id's from 500-599.
        // We test for the case that this was the last batch of messages for the narrow
        // so no more fetching should occur.
        // And also while fetching for the above condition the server received a new message
        // event, updating the last message's id for that narrow to 600 from 599.
        data.resp.found_newest = true;
        msg_list.data.fetch_status.update_expected_max_message_id([{id: 600}]);

        test_happy_path({
            msg_list,
            data,
        });

        // To handle this special case we should allow another fetch to occur,
        // since the last message event's data had been discarded.
        // This fetch goes on until the newest message has been found.
        assert.equal(msg_list.data.fetch_status.can_load_newer_messages(), false);
    })();

    (function test_home() {
        reset_lists();
        const msg_list = message_lists.home;

        const data = [
            {
                req: {
                    anchor: "444",
                    num_before: 0,
                    num_after: 100,
                    client_gravatar: true,
                },
                resp: {
                    messages: message_range(500, 600),
                    found_newest: false,
                },
            },
            {
                req: {
                    anchor: "599",
                    num_before: 0,
                    num_after: 100,
                    client_gravatar: true,
                },
                resp: {
                    messages: message_range(700, 800),
                    found_newest: true,
                },
            },
        ];

        test_happy_path({
            msg_list,
            data: data[0],
            empty_msg_list: true,
        });

        all_messages_data.append(message_range(444, 445), false);

        test_happy_path({
            msg_list,
            data: data[0],
            empty_msg_list: false,
        });

        assert.equal(msg_list.data.fetch_status.can_load_newer_messages(), true);

        test_happy_path({
            msg_list,
            data: data[1],
        });

        assert.equal(msg_list.data.fetch_status.can_load_newer_messages(), false);
    })();
});

"use strict";

const _ = require("lodash");

set_global("$", global.make_zjquery());
set_global("document", "document-stub");

zrequire("message_fetch");

const noop = () => {};

function MessageListView() {
    return {};
}
set_global("MessageListView", MessageListView);

zrequire("FetchStatus", "js/fetch_status");
zrequire("Filter", "js/filter");
zrequire("MessageListData", "js/message_list_data");
zrequire("message_list");
const people = zrequire("people");

set_global("recent_topics", {
    process_messages: noop,
});
// Still required for page_params.initial_pointer
set_global("page_params", {});
set_global("ui_report", {
    hide_error: noop,
});

set_global("channel", {});
set_global("document", "document-stub");
set_global("message_scroll", {
    show_loading_older: noop,
    hide_loading_older: noop,
    show_loading_newer: noop,
    hide_loading_newer: noop,
    update_top_of_narrow_notices: () => {},
});
set_global("message_util", {});
set_global("message_store", {});
set_global("narrow_state", {});
set_global("pm_list", {});
set_global("server_events", {});
set_global("stream_list", {
    maybe_scroll_narrow_into_view: () => {},
});

const alice = {
    email: "alice@example.com",
    user_id: 7,
    full_name: "Alice",
};
people.add_active_user(alice);

server_events.home_view_loaded = noop;

function stub_message_view(list) {
    list.view.append = noop;
    list.view.maybe_rerender = noop;
    list.view.prepend = noop;
}

function make_home_msg_list() {
    const table_name = "whatever";
    const filter = new Filter();

    const list = new message_list.MessageList({
        table_name,
        filter,
    });
    return list;
}

function make_all_list() {
    return new message_list.MessageList({});
}

function reset_lists() {
    set_global("home_msg_list", make_home_msg_list());
    set_global("current_msg_list", home_msg_list);
    message_list.all = make_all_list();
    stub_message_view(home_msg_list);
    stub_message_view(message_list.all);
}

function config_fake_channel(conf) {
    const self = {};
    let called;

    channel.get = function (opts) {
        if (called && !conf.can_call_again) {
            throw "only use this for one call";
        }
        if (!conf.can_call_again) {
            assert(self.success === undefined);
        }
        assert.equal(opts.url, "/json/messages");
        assert.deepEqual(opts.data, conf.expected_opts_data);
        self.success = opts.success;
        called = true;
    };

    return self;
}

function config_process_results(messages) {
    const self = {};

    const messages_processed_for_bools = [];

    message_store.set_message_booleans = function (message) {
        messages_processed_for_bools.push(message);
    };

    message_store.add_message_metadata = (message) => message;

    message_util.do_unread_count_updates = function (arg) {
        assert.deepEqual(arg, messages);
    };

    message_util.add_old_messages = function (new_messages, msg_list) {
        assert.deepEqual(new_messages, messages);
        msg_list.add_messages(new_messages);
    };

    stream_list.update_streams_sidebar = noop;

    pm_list.update_private_messages = noop;

    self.verify = function () {
        assert.deepEqual(messages_processed_for_bools, messages);
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

function initial_fetch_step() {
    const self = {};

    let fetch;
    const response = initialize_data.initial_fetch.resp;

    self.prep = function () {
        fetch = config_fake_channel({
            expected_opts_data: initialize_data.initial_fetch.req,
        });

        message_fetch.initialize();
    };

    self.finish = function () {
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

    self.prep = function () {
        fetch = config_fake_channel({
            expected_opts_data: initialize_data.forward_fill.req,
        });
    };

    self.finish = function () {
        const response = initialize_data.forward_fill.resp;

        let idle_config;
        $("document-stub").idle = function (config) {
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

    const step1 = initial_fetch_step();

    step1.prep();

    const step2 = forward_fill_step();

    step2.prep();
    step1.finish();

    const idle_config = step2.finish();

    test_backfill_idle(idle_config);
});

function simulate_narrow() {
    const filter = {
        predicate: () => () => false,
    };

    narrow_state.active = function () {
        return true;
    };
    narrow_state.public_operators = function () {
        return [{operator: "pm-with", operand: alice.email}];
    };

    const msg_list = new message_list.MessageList({
        table_name: "zfilt",
        filter,
    });
    set_global("current_msg_list", msg_list);

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

        const data = {
            req: {
                anchor: "444",
                num_before: 0,
                num_after: 100,
                narrow: `[{"operator":"pm-with","operand":[${alice.user_id}]}]`,
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
        const msg_list = home_msg_list;

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

        message_list.all.append_to_view = () => {};
        message_list.all.append(message_range(444, 445), false);

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

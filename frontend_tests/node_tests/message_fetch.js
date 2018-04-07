set_global('$', global.make_zjquery());
set_global('document', 'document-stub');

zrequire('message_fetch');

var noop = function () {};

set_global('MessageListView', function () { return {}; });

zrequire('FetchStatus', 'js/fetch_status');
zrequire('Filter', 'js/filter');
zrequire('message_list');
zrequire('util');

set_global('page_params', {
    have_initial_messages: true,
    pointer: 444,
});

set_global('activity', {});
set_global('channel', {});
set_global('document', 'document-stub');
set_global('message_util', {});
set_global('message_store', {});
set_global('muting', {});
set_global('narrow_state', {});
set_global('pm_list', {});
set_global('resize', {});
set_global('server_events', {});
set_global('stream_list', {});

muting.is_topic_muted = function () { return false; };
resize.resize_bottom_whitespace = noop;
server_events.home_view_loaded = noop;

function stub_message_view(list) {
    list.view.append = noop;
    list.view.maybe_rerender = noop;
    list.view.prepend = noop;
}

function make_home_msg_list() {
    var table_name = 'whatever';
    var filter = new Filter();
    var opts = {};

    var list = new message_list.MessageList(table_name, filter, opts);
    return list;
}

function make_all_list() {
    return new message_list.MessageList();
}

function reset_lists() {
    set_global('home_msg_list', make_home_msg_list());
    set_global('current_msg_list', home_msg_list);
    message_list.all = make_all_list();
    stub_message_view(home_msg_list);
    stub_message_view(message_list.all);
}

function config_fake_channel(conf) {
    var self = {};
    var called;

    channel.get = function (opts) {
        if (called) {
            throw "only use this for one call";
        }
        assert(self.success === undefined);
        assert.equal(opts.url, '/json/messages');
        assert.deepEqual(opts.data, conf.expected_opts_data);
        self.success = opts.success;
        called = true;
    };

    return self;
}

function config_process_results(messages) {
    var self = {};

    var messages_processed_for_bools = [];

    message_store.set_message_booleans = function (message) {
        messages_processed_for_bools.push(message);
    };

    message_util.do_unread_count_updates = function (arg) {
        assert.deepEqual(arg, messages);
    };

    message_util.add_messages = function (new_messages, msg_list, opts) {
        assert.deepEqual(new_messages, messages);
        msg_list.add_messages(new_messages, opts);
    };

    activity.process_loaded_messages = function (arg) {
        assert.deepEqual(arg, messages);
    };

    stream_list.update_streams_sidebar = noop;

    pm_list.update_private_messages = noop;

    self.verify = function () {
        assert.deepEqual(messages_processed_for_bools, messages);
    };

    return self;
}

function message_range(start, end) {
    return _.map(_.range(start, end), function (idx) {
        return { id: idx };
    });
}

var initialize_data = {
    initial_fetch: {
        req: {
            anchor: 444,
            num_before: 200,
            num_after: 200,
            client_gravatar: true,
        },
        resp: {
            messages: message_range(201, 801),
            found_newest: false,
        },
    },

    forward_fill: {
        req: {
            anchor: '800',
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
            anchor: '201',
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
    var response = opts.response;
    var messages = response.messages;

    var process_results = config_process_results(messages);
    opts.fetch.success(response);
    process_results.verify();
}

function initial_fetch_step() {
    var self = {};

    var fetch;
    var response = initialize_data.initial_fetch.resp;

    self.prep = function () {
        fetch = config_fake_channel({
            expected_opts_data: initialize_data.initial_fetch.req,
        });

        message_fetch.initialize();
    };

    self.finish = function () {
        test_fetch_success({
            fetch: fetch,
            response: response,
        });
    };

    return self;
}

function forward_fill_step() {
    var self = {};

    var fetch;

    self.prep = function () {
        fetch = config_fake_channel({
            expected_opts_data: initialize_data.forward_fill.req,
        });
    };

    self.finish = function () {
        var response = initialize_data.forward_fill.resp;

        var idle_config;
        $('document-stub').idle = function (config) {
            idle_config = config;
        };

        test_fetch_success({
            fetch: fetch,
            response: response,
        });

        assert.equal(idle_config.idle, 10000);

        return idle_config;
    };

    return self;
}

function test_backfill_idle(idle_config) {
    var fetch = config_fake_channel({
        expected_opts_data: initialize_data.back_fill.req,
    });

    var response = initialize_data.back_fill.resp;

    idle_config.onIdle();

    test_fetch_success({
        fetch: fetch,
        response: response,
    });
}

(function test_initialize() {
    reset_lists();

    var step1 = initial_fetch_step();

    step1.prep();

    var step2 = forward_fill_step();

    step2.prep();
    step1.finish();

    var idle_config = step2.finish();

    test_backfill_idle(idle_config);
}());


function simulate_narrow() {
    var filter = {
        predicate: function () { return true; },
    };

    narrow_state.active = function () { return true; };
    narrow_state.public_operators = function () {
        return 'operators-stub';
    };

    var msg_list = new message_list.MessageList(
        'zfilt',
        filter
    );
    set_global('current_msg_list', msg_list);

    return msg_list;
}

(function test_loading_newer() {
    function test_dup_new_fetch(msg_list) {
        assert.equal(msg_list.fetch_status.can_load_newer_messages(), false);
        message_fetch.maybe_load_newer_messages({
            msg_list: msg_list,
        });
    }

    function test_happy_path(opts) {
        var msg_list = opts.msg_list;
        var data = opts.data;

        var fetch = config_fake_channel({
            expected_opts_data: data.req,
        });

        message_fetch.maybe_load_newer_messages({
            msg_list: msg_list,
        });

        test_dup_new_fetch(msg_list);

        test_fetch_success({
            fetch: fetch,
            response: data.resp,
        });
    }

    (function test_narrow() {
        var msg_list = simulate_narrow();

        var data = {
            req: {
                anchor: '444',
                num_before: 0,
                num_after: 100,
                narrow: '"operators-stub"',
                client_gravatar: true,
            },
            resp: {
                messages: message_range(500, 600),
                found_newest: false,
            },
        };

        test_happy_path({
            msg_list: msg_list,
            data: data,
        });

        assert.equal(msg_list.fetch_status.can_load_newer_messages(), true);
    }());

    (function test_home() {
        reset_lists();
        var msg_list = home_msg_list;

        var data = [
            {
                req: {
                    anchor: '444',
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
                    anchor: '599',
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
            msg_list: msg_list,
            data: data[0],
        });

        assert.equal(msg_list.fetch_status.can_load_newer_messages(), true);

        test_happy_path({
            msg_list: msg_list,
            data: data[1],
        });

        assert.equal(msg_list.fetch_status.can_load_newer_messages(), false);

    }());

}());

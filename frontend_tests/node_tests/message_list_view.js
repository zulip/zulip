set_global('$', global.make_zjquery());
set_global('document', 'document-stub');

zrequire('util');
zrequire('XDate', 'node_modules/xdate/src/xdate');
zrequire('Filter', 'js/filter');
zrequire('FetchStatus', 'js/fetch_status');
zrequire('MessageListView', 'js/message_list_view');
zrequire('message_list');

var noop = function () {};

set_global('page_params', {
  twenty_four_hour_time: false,
});
set_global('home_msg_list', null);
set_global('feature_flags', {twenty_four_hour_time: false});
set_global('people', {small_avatar_url: function () { return ''; }});
set_global('unread', {message_unread: function () {}});
// timerender calls setInterval when imported
set_global('timerender', {
    render_date: function (time1, time2) {
        if (time2 === undefined) {
            return [{outerHTML: String(time1.getTime())}];
        }
        return [{outerHTML: String(time1.getTime()) + ' - ' + String(time2.getTime())}];
    },
    stringify_time : function (time) {
        if (page_params.twenty_four_hour_time) {
            return time.toString('HH:mm');
        }
        return time.toString('h:mm TT');
    },
});

set_global('rows', {
    get_table: function () {
        return {
            children: function () {
                return {
                    detach: noop,
                };
            },
        };
    },
});

(function test_merge_message_groups() {
    // MessageListView has lots of DOM code, so we are going to test the message
    // group mearging logic on its own.

    function build_message_context(message, message_context) {
        if (message_context === undefined) {
            message_context = {};
        }
        if (message === undefined) {
            message = {};
        }
        message_context = _.defaults(message_context, {
            include_sender: true,
        });
        message_context.msg = _.defaults(message, {
            id: _.uniqueId('test_message_'),
            status_message: false,
            type: 'stream',
            stream: 'Test Stream 1',
            subject: 'Test Subject 1',
            sender_email: 'test@example.com',
            timestamp: _.uniqueId(),
        });
        return message_context;
    }

    function build_message_group(messages) {
        return {
            message_containers: messages,
            message_group_id: _.uniqueId('test_message_group_'),
            show_date: true,
        };
    }

    function build_list(message_groups) {
        var list = new MessageListView(undefined, undefined, true);
        list._message_groups = message_groups;
        list.list = {
            unsubscribed_bookend_content: function () {},
            subscribed_bookend_content: function () {},
        };
        return list;
    }

    function assert_message_list_equal(list1, list2) {
        assert.deepEqual(
            _.chain(list1).pluck('msg').pluck('id').value(),
            _.chain(list2).pluck('msg').pluck('id').value());
    }

    function assert_message_groups_list_equal(list1, list2) {
        function extract_message_ids(message_group) {
            return _.chain(message_group.messages)
                .pluck('msg')
                .pluck('id')
                .value();
        }
        assert.deepEqual(
            _.map(list1, extract_message_ids),
            _.map(list2, extract_message_ids));
    }

    (function test_empty_list_bottom() {
        var list = build_list([]);
        var message_group = build_message_group([
            build_message_context(),
        ]);

        var result = list.merge_message_groups([message_group], 'bottom');

        assert_message_groups_list_equal(list._message_groups, [message_group]);
        assert_message_groups_list_equal(result.append_groups, [message_group]);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_append_message_same_subject() {

        var message1 = build_message_context();
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context();
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'bottom');

        assert_message_groups_list_equal(
            list._message_groups,
            [build_message_group([message1, message2])]);
        assert_message_groups_list_equal(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, [message2]);
        assert_message_list_equal(result.rerender_messages, [message1]);
    }());

    (function test_append_message_diffrent_subject() {

        var message1 = build_message_context();
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({subject: 'Test subject 2'});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'bottom');

        assert(!message_group2.show_date);
        assert_message_groups_list_equal(
            list._message_groups,
            [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_append_message_diffrent_day() {

        var message1 = build_message_context({timestamp: 1000});
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({timestamp: 900000});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'bottom');

        assert(message_group2.show_date);
        assert_message_groups_list_equal(
            list._message_groups,
            [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_append_message_historical() {

        var message1 = build_message_context({historical: false});
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({historical: true});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'bottom');

        assert(message_group2.bookend_top);
        assert_message_groups_list_equal(
            list._message_groups,
            [message_group1, message_group2]);
        assert_message_groups_list_equal(result.append_groups, [message_group2]);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_append_message_same_subject_me_message() {

        var message1 = build_message_context();
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({is_me_message: true});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'bottom');

        assert(message2.include_sender);
        assert_message_groups_list_equal(
            list._message_groups,
            [build_message_group([message1, message2])]);
        assert_message_groups_list_equal(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, [message2]);
        assert_message_list_equal(result.rerender_messages, [message1]);
    }());


    (function test_prepend_message_same_subject() {

        var message1 = build_message_context();
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context();
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'top');

        assert_message_groups_list_equal(
            list._message_groups,
            [build_message_group([message2, message1])]);
        assert_message_groups_list_equal(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, []);
        assert_message_groups_list_equal(result.rerender_groups,
            [build_message_group([message2, message1])]);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_prepend_message_diffrent_subject() {

        var message1 = build_message_context();
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({subject: 'Test Subject 2'});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'top');

        assert_message_groups_list_equal(
            list._message_groups,
            [message_group2, message_group1]);
        assert_message_groups_list_equal(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_prepend_message_diffrent_day() {

        var message1 = build_message_context({timestamp: 900000});
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({timestamp: 1000});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'top');

        assert.equal(
            message_group1.show_date,
            '900000000 - 1000000');
        assert_message_groups_list_equal(
            list._message_groups,
            [message_group2, message_group1]);
        assert_message_groups_list_equal(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert_message_groups_list_equal(result.rerender_groups, [message_group1]);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

    (function test_prepend_message_historical() {

        var message1 = build_message_context({historical: false});
        var message_group1 = build_message_group([
            message1,
        ]);

        var message2 = build_message_context({historical: true});
        var message_group2 = build_message_group([
            message2,
        ]);

        var list = build_list([message_group1]);
        var result = list.merge_message_groups([message_group2], 'top');

        assert(message_group1.bookend_top);
        assert_message_groups_list_equal(
            list._message_groups,
            [message_group2, message_group1]);
        assert_message_groups_list_equal(result.append_groups, []);
        assert_message_groups_list_equal(result.prepend_groups, [message_group2]);
        assert_message_groups_list_equal(result.rerender_groups, []);
        assert_message_list_equal(result.append_messages, []);
        assert_message_list_equal(result.rerender_messages, []);
    }());

}());

(function test_render_windows() {
    // We only render up to 400 messages at a time in our message list,
    // and we only change the window (which is a range, really, with
    // start/end) when the pointer moves outside of the window or close
    // to the edges.

    var view = (function make_view() {
        var table_name = 'zfilt';
        var filter = new Filter();
        var opts = {};

        var list = new message_list.MessageList(table_name, filter, opts);
        var view = list.view;

        // Stub out functionality that is not core to the rendering window
        // logic.
        list.unmuted_messages = function (messages) {
            return messages;
        };

        // We don't need to actually render the DOM.  The windowing logic
        // sits above that layer.
        view.render = noop;
        view.rerender_preserving_scrolltop = noop;

        return view;
    }());

    var list = view.list;

    (function test_with_empty_list() {
        // The function should early exit here.
        var rendered = view.maybe_rerender();
        assert.equal(rendered, false);
    }());

    var messages;

    function reset_list(opts) {
        messages = _.map(_.range(opts.count), function (i) {
            return {
                id: i,
            };
        });
        list.selected_idx = function () { return 0; };
        list.clear();

        list.add_messages(messages, {});
    }


    function verify_no_move_range(start, end) {
        // In our render window, there are up to 300 positions in
        // the list where we can move the pointer without forcing
        // a re-render.  The code avoids hasty re-renders for
        // performance reasons.
        _.each(_.range(start, end), function (idx) {
            list.selected_idx = function () { return idx; };
            var rendered = view.maybe_rerender();
            assert.equal(rendered, false);
        });
    }

    function verify_move(idx, range) {
        var start = range[0];
        var end = range[1];

        list.selected_idx = function () { return idx; };
        var rendered = view.maybe_rerender();
        assert.equal(rendered, true);
        assert.equal(view._render_win_start, start);
        assert.equal(view._render_win_end, end);
    }

    reset_list({count: 51});
    verify_no_move_range(0, 51);

    reset_list({count: 450});
    verify_no_move_range(0, 350);

    verify_move(350, [150, 450]);
    verify_no_move_range(200, 400);

    verify_move(199, [0, 400]);
    verify_no_move_range(50, 350);

    verify_move(350, [150, 450]);
    verify_no_move_range(200, 400);

    verify_move(199, [0, 400]);
    verify_no_move_range(0, 350);

    verify_move(400, [200, 450]);

    reset_list({count: 800});
    verify_no_move_range(0, 350);

    verify_move(350, [150, 550]);
    verify_no_move_range(200, 500);

    verify_move(500, [300, 700]);
    verify_no_move_range(350, 650);

    verify_move(650, [450, 800]);
    verify_no_move_range(500, 750);

    verify_move(499, [299, 699]);
    verify_no_move_range(349, 649);

    verify_move(348, [148, 548]);
    verify_no_move_range(198, 398);

    verify_move(197, [0, 400]);
    verify_no_move_range(0, 350);
}());

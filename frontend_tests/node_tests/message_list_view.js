var _ = require('node_modules/underscore/underscore.js');
var MessageListView = require('js/message_list_view.js');

add_dependencies({
    XDate: 'node_modules/xdate/src/xdate.js',
    util: 'js/util.js',
});

set_global('page_params', {
  twenty_four_hour_time: false,
});
set_global('home_msg_list', null);
set_global('feature_flags', {twenty_four_hour_time: false});
set_global('people', {small_avatar_url: function () { return ''; }});
set_global('notifications', {speaking_at_me: function () {}});
set_global('unread', {message_unread: function () {}});
// timerender calls setInterval when imported
set_global('timerender', {
    render_date: function (time1, time2) {
        if (time2 === undefined) {
            return [{outerHTML: String(time1.getTime())}];
        }
        return [{outerHTML: String(time1.getTime()) + ' - ' + String(time2.getTime())}];
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

        assert(message_group1.bookend_bottom);
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

        assert(message_group2.bookend_bottom);
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

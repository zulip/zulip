// These unit tests for static/js/message_list.js emphasize the model-ish
// aspects of the MessageList class.  We have to stub out a few functions
// related to views and events to get the tests working.

var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js',
    util: 'js/util.js',
    Dict: 'js/dict.js',
    muting: 'js/muting.js',
    MessageListView: 'js/message_list_view.js'
});


set_global('document', null);
set_global('$', function () {
    return {
        on: function () {},
        trigger: function () {}
    };
});

set_global('feature_flags', {});

var MessageList = require('js/message_list');

(function test_basics() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);

    var messages = [
        {
            id: 50,
            content: 'fifty'
        },
        {
            id: 60
        },
        {
            id: 70
        },
        {
            id: 80
        }
    ];

    assert.equal(list.empty(), true);

    list.append(messages, true);

    assert.equal(list.empty(), false);
    assert.equal(list.first().id, 50);
    assert.equal(list.last().id, 80);

    assert.equal(list.get(50).content, 'fifty');

    assert.equal(list.closest_id(49), 50);
    assert.equal(list.closest_id(50), 50);
    assert.equal(list.closest_id(51), 50);
    assert.equal(list.closest_id(59), 60);
    assert.equal(list.closest_id(60), 60);
    assert.equal(list.closest_id(61), 60);

    assert.deepEqual(list.all(), messages);

    global.$.Event = function (ev) {
        assert.equal(ev, 'message_selected.zulip');
    };
    list.select_id(50);

    assert.equal(list.selected_id(), 50);

    list.advance_past_messages([60, 80]);
    assert.equal(list.selected_id(), 60);

    var old_messages = [
        {
            id: 30
        },
        {
            id: 40
        }
    ];
    list.prepend(old_messages, true);
    assert.equal(list.first().id, 30);
    assert.equal(list.last().id, 80);

    var new_messages = [
        {
            id: 90
        }
    ];
    list.append(new_messages, true);
    assert.equal(list.last().id, 90);


    list.view.clear_table = function () {};
    list.clear();
    assert.deepEqual(list.all(), []);

}());

(function test_nth_most_recent_id() {
    var table;
    var filter = {};

    var list = new MessageList(table, filter);
    list.append([{id:10}, {id:20}, {id:30}]);
    assert.equal(list.nth_most_recent_id(1), 30);
    assert.equal(list.nth_most_recent_id(2), 20);
    assert.equal(list.nth_most_recent_id(3), 10);
    assert.equal(list.nth_most_recent_id(4), -1);
}());

(function test_message_counting() {
    global.feature_flags.summarize_read_while_narrowed = true;
    var list = new MessageList(undefined, {}, {summarize_read: 'home'});

    var summarized_flags = ['summarize_in_home'];
    var unsummarized_flags = [];

    list.append([
        {id: 10, flags: unsummarized_flags},
        {id: 20, flags: unsummarized_flags},
        {id: 30, flags: summarized_flags},
        {id: 40, flags: summarized_flags},
        {id: 50, flags: unsummarized_flags},
        {id: 60, flags: summarized_flags}
    ]);
    list.min_id_exempted_from_summaries = 10000;

    assert.equal(list.count_full_messages_between(1, 5), 2);
    assert.equal(list.idx_full_messages_before(5, 2), 1);
    assert.equal(list.idx_full_messages_before(5, 10), 0);
    assert.equal(list.idx_full_messages_after(0, 3), 5);
    assert.equal(list.idx_full_messages_after(0, 10), 6);

}());

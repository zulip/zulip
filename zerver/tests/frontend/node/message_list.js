// These unit tests for static/js/message_list.js emphasize the model-ish
// aspects of the MessageList class.  We have to stub out a few functions
// related to views and events to get the tests working.

var assert = require('assert');

(function set_up_dependencies () {
    global.document = null;
    global.$ = function () {
        return {
            on: function () {},
            trigger: function () {}
        };
    };

    global._ = require('third/underscore/underscore.js');
    global.util = require('js/util.js');
    global.feature_flags = {};

}());

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


    list._clear_table = function () {};
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

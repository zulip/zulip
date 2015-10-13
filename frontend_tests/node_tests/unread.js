// Unit test the unread.js module, which depends on these global variables:
//
//   _, narrow, current_msg_list, home_msg_list, subs
//
// These tests are framework-free and run sequentially; they are invoked
// immediately after being defined.  The contract here is that tests should
// clean up after themselves, and they should explicitly stub all
// dependencies (except _).

add_dependencies({
    muting: 'js/muting.js'
});

var stream_data = require('js/stream_data.js');

stream_data = {
    canonicalized_name: stream_data.canonicalized_name
};
set_global('stream_data', stream_data);

var Dict = global.Dict;
var muting = global.muting;
var unread = require('js/unread.js');

var narrow = {};
global.narrow = narrow;

var current_msg_list = {};
global.current_msg_list = current_msg_list;

var home_msg_list = {};
global.home_msg_list = home_msg_list;

var zero_counts = {
    private_message_count: 0,
    home_unread_messages: 0,
    mentioned_message_count: 0,
    stream_count: new Dict(),
    subject_count: new Dict(),
    pm_count: new Dict(),
    unread_in_current_view: 0
};

(function test_empty_counts_while_narrowed() {
    narrow.active = function () {
        return true;
    };
    current_msg_list.all = function () {
        return [];
    };

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_empty_counts_while_home() {
    narrow.active = function () {
        return false;
    };
    current_msg_list.all = function () {
        return [];
    };

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_changing_subjects() {
    // Summary: change the subject of a message from 'lunch'
    // to 'dinner' using update_unread_subjects().
    var count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, 0);

    var message = {
        id: 15,
        type: 'stream',
        stream: 'social',
        subject: 'lunch'
    };

    var other_message = {
        id: 16,
        type: 'stream',
        stream: 'social',
        subject: 'lunch'
    };

    unread.process_loaded_messages([message, other_message]);

    count = unread.num_unread_for_subject('Social', 'lunch');
    assert.equal(count, 2);

    var event = {
        subject: 'dinner'
    };

    unread.update_unread_subjects(message, event);

    count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, 1);

    count = unread.num_unread_for_subject('social', 'dinner');
    assert.equal(count, 1);

    event = {
        subject: 'snack'
    };

    unread.update_unread_subjects(other_message, event);

    count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, 0);

    count = unread.num_unread_for_subject('social', 'snack');
    assert.equal(count, 1);

    // Test defensive code.  Trying to update a message we don't know
    // about should be a no-op.
    var unknown_message = {
        id: 18,
        type: 'stream',
        stream: 'social',
        subject: 'lunch'
    };
    event = {
        subject: 'brunch'
    };
    unread.update_unread_subjects(other_message, event);

    // cleanup
    message.subject = 'dinner';
    unread.process_read_message(message);
    count = unread.num_unread_for_subject('social', 'dinner');
    assert.equal(count, 0);

    other_message.subject = 'snack';
    unread.process_read_message(other_message);
    count = unread.num_unread_for_subject('social', 'snack');
    assert.equal(count, 0);
}());

(function test_muting() {
    stream_data.is_subscribed = function () {
        return true;
    };

    stream_data.in_home_view = function () {
        return true;
    };

    unread.declare_bankruptcy();

    var message = {
        id: 15,
        type: 'stream',
        stream: 'social',
        subject: 'test_muting'
    };

    unread.process_loaded_messages([message]);
    var counts = unread.get_counts();
    assert.equal(counts.stream_count.get('social'), 1);
    assert.equal(counts.home_unread_messages, 1);

    muting.mute_topic('social', 'test_muting');
    counts = unread.get_counts();
    assert.equal(counts.stream_count.get('social'), 0);
    assert.equal(counts.home_unread_messages, 0);
}());

(function test_num_unread_for_subject() {
    // Test the num_unread_for_subject() function using many
    // messages.
    unread.declare_bankruptcy();

    var count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, 0);

    var message = {
        type: 'stream',
        stream: 'social',
        subject: 'lunch'
    };

    var num_msgs = 10000;
    var i;
    for (i = 0; i < num_msgs; ++i) {
        message.id = i+1;
        unread.process_loaded_messages([message]);
    }

    count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, num_msgs);

    for (i = 0; i < num_msgs; ++i) {
        message.id = i+1;
        unread.process_read_message(message);
    }

    count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, 0);
}());


(function test_home_messages() {
    narrow.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };
    stream_data.in_home_view = function () {
        return true;
    };

    var message = {
        id: 15,
        type: 'stream',
        stream: 'social',
        subject: 'lunch'
    };

    home_msg_list.get = function (msg_id) {
        return (msg_id === '15') ? message : undefined;
    };

    var counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(counts.stream_count.get('social'), 1);
    unread.process_read_message(message);
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);

    // Now unsubscribe all our streams.
    stream_data.is_subscribed = function () {
        return false;
    };
    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

}());

(function test_phantom_messages() {
    var message = {
        id: 999,
        type: 'stream',
        stream: 'foo',
        subject: 'phantom'
    };

    unread.process_read_message(message);
    var counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
}());

(function test_private_messages() {
    narrow.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };

    var counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);

    var message = {
        id: 15,
        type: 'private',
        reply_to: 'alice@zulip.com'
    };

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 1);
    unread.process_read_message(message);
    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);

    // Test unknown message is harmless
    message = {
        id: 9,
        type: 'private',
        reply_to: 'unknown@zulip.com'
    };

    unread.process_read_message(message);
    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
}());

(function test_num_unread_for_person() {
    var email = 'unknown@zulip.com';
    assert.equal(unread.num_unread_for_person(email), 0);

    email = 'alice@zulip.com';
    assert.equal(unread.num_unread_for_person(email), 0);

    var message = {
        id: 15,
        reply_to: email,
        type: 'private'
    };

    var read_message = {
        flags: ['read']
    };
    unread.process_loaded_messages([message, read_message]);
    assert.equal(unread.num_unread_for_person(email), 1);
}());


(function test_mentions() {
    narrow.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };

    var counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 0);

    var message = {
        id: 15,
        type: 'stream',
        stream: 'social',
        subject: 'lunch',
        mentioned: true
    };

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 1);
    unread.process_read_message(message);
    counts = unread.get_counts();
    assert.equal(counts.mentioned_message_count, 0);
}());

(function test_declare_bankruptcy() {
    unread.declare_bankruptcy();

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_num_unread_current_messages() {
    var count = unread.num_unread_current_messages();
    assert.equal(count, 0);

    var message = {
        id: 15
    };
    current_msg_list.all = function () {
        return [message];
    };

    // It's a little suspicious that num_unread_current_messages()
    // is using the pointer as a hint for filtering out unread
    // messages, but right now, it's impossible for unread messages
    // to be above the pointer in a narrowed view, so unread.js uses
    // this for optimization purposes.
    current_msg_list.selected_id = function () {
        return 11; // less than our message's id
    };

    count = unread.num_unread_current_messages();
    assert.equal(count, 1);
}());


(function test_message_unread() {
    // Test some code that might be overly defensive, for line coverage sake.
    assert(!unread.message_unread(undefined));
    assert(unread.message_unread({flags: []}));
    assert(!unread.message_unread({flags: ['read']}));
}());


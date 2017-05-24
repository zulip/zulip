// Unit test the unread.js module, which depends on these global variables:
//
//   _, narrow_state, current_msg_list, home_msg_list, subs
//
// These tests are framework-free and run sequentially; they are invoked
// immediately after being defined.  The contract here is that tests should
// clean up after themselves, and they should explicitly stub all
// dependencies (except _).

add_dependencies({
    muting: 'js/muting.js',
    people: 'js/people.js',
    unread: 'js/unread.js',
});

var stream_data = require('js/stream_data.js');

stream_data = {
    canonicalized_name: stream_data.canonicalized_name,
};
set_global('stream_data', stream_data);
set_global('blueslip', {});

var Dict = global.Dict;
var muting = global.muting;
var people = global.people;

var unread = require('js/unread.js');

var narrow_state = {};
global.narrow_state = narrow_state;

var current_msg_list = {};
global.current_msg_list = current_msg_list;

var home_msg_list = {};
global.home_msg_list = home_msg_list;

var me = {
    email: 'me@example.com',
    user_id: 30,
    full_name: 'Me Myself',
};
people.add(me);
people.initialize_current_user(me.user_id);

var zero_counts = {
    private_message_count: 0,
    home_unread_messages: 0,
    mentioned_message_count: 0,
    stream_count: new Dict(),
    subject_count: new Dict(),
    pm_count: new Dict(),
    unread_in_current_view: 0,
};

(function test_empty_counts_while_narrowed() {
    narrow_state.active = function () {
        return true;
    };
    current_msg_list.all_messages = function () {
        return [];
    };

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_empty_counts_while_home() {
    narrow_state.active = function () {
        return false;
    };
    current_msg_list.all_messages = function () {
        return [];
    };

    var counts = unread.get_counts();
    assert.deepEqual(counts, zero_counts);
}());

(function test_changing_subjects() {
    // Summary: change the subject of a message from 'lunch'
    // to 'dinner' using update_unread_topics().
    var count = unread.num_unread_for_subject('social', 'lunch');
    assert.equal(count, 0);

    var stream_id = 100;
    var wrong_stream_id = 110;

    var message = {
        id: 15,
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunch',
    };

    var other_message = {
        id: 16,
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunch',
    };

    unread.process_loaded_messages([message, other_message]);

    count = unread.num_unread_for_subject(stream_id, 'lunch');
    assert.equal(count, 2);
    assert(unread.topic_has_any_unread(stream_id, 'lunch'));
    assert(!unread.topic_has_any_unread(wrong_stream_id, 'lunch'));

    var event = {
        subject: 'dinner',
    };

    unread.update_unread_topics(message, event);

    count = unread.num_unread_for_subject(stream_id, 'lunch');
    assert.equal(count, 1);

    count = unread.num_unread_for_subject(stream_id, 'dinner');
    assert.equal(count, 1);

    event = {
        subject: 'snack',
    };

    unread.update_unread_topics(other_message, event);

    count = unread.num_unread_for_subject(stream_id, 'lunch');
    assert.equal(count, 0);
    assert(!unread.topic_has_any_unread(stream_id, 'lunch'));
    assert(!unread.topic_has_any_unread(wrong_stream_id, 'lunch'));

    count = unread.num_unread_for_subject(stream_id, 'snack');
    assert.equal(count, 1);
    assert(unread.topic_has_any_unread(stream_id, 'snack'));
    assert(!unread.topic_has_any_unread(wrong_stream_id, 'snack'));

    // Test defensive code.  Trying to update a message we don't know
    // about should be a no-op.
    event = {
        subject: 'brunch',
    };
    unread.update_unread_topics(other_message, event);

    // cleanup
    message.subject = 'dinner';
    unread.process_read_message(message);
    count = unread.num_unread_for_subject(stream_id, 'dinner');
    assert.equal(count, 0);

    other_message.subject = 'snack';
    unread.process_read_message(other_message);
    count = unread.num_unread_for_subject(stream_id, 'snack');
    assert.equal(count, 0);
}());

stream_data.get_stream_id = function () {
    return 999;
};

(function test_muting() {
    stream_data.is_subscribed = function () {
        return true;
    };

    stream_data.in_home_view = function () {
        return true;
    };

    unread.declare_bankruptcy();

    var stream_id = 101;
    var unknown_stream_id = 555;

    stream_data.get_sub_by_id = function (stream_id) {
        if (stream_id === 101) {
            return {name: 'social'};
        }
    };

    var message = {
        id: 15,
        type: 'stream',
        stream_id: stream_id,
        subject: 'test_muting',
    };

    unread.process_loaded_messages([message]);
    var counts = unread.get_counts();
    assert.equal(counts.stream_count.get(stream_id), 1);
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(unread.num_unread_for_stream(stream_id), 1);

    muting.add_muted_topic('social', 'test_muting');
    counts = unread.get_counts();
    assert.equal(counts.stream_count.get(stream_id), 0);
    assert.equal(counts.home_unread_messages, 0);
    assert.equal(unread.num_unread_for_stream(stream_id), 0);

    assert.equal(unread.num_unread_for_stream(unknown_stream_id), 0);
}());

(function test_num_unread_for_subject() {
    // Test the num_unread_for_subject() function using many
    // messages.
    unread.declare_bankruptcy();

    var stream_id = 301;
    var count = unread.num_unread_for_subject(stream_id, 'lunch');
    assert.equal(count, 0);

    var message = {
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunch',
    };

    var num_msgs = 500;
    var i;
    for (i = 0; i < num_msgs; i += 1) {
        message.id = i+1;
        unread.process_loaded_messages([message]);
    }

    count = unread.num_unread_for_subject(stream_id, 'lunch');
    assert.equal(count, num_msgs);

    for (i = 0; i < num_msgs; i += 1) {
        message.id = i+1;
        unread.process_read_message(message);
    }

    count = unread.num_unread_for_subject(stream_id, 'lunch');
    assert.equal(count, 0);
}());


(function test_home_messages() {
    narrow_state.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };
    stream_data.in_home_view = function () {
        return true;
    };

    var stream_id = 401;

    stream_data.get_sub_by_id = function () {
        return {
            name: 'whatever',
        };
    };

    var message = {
        id: 15,
        type: 'stream',
        stream_id: stream_id,
        subject: 'lunch',
    };

    home_msg_list.get = function (msg_id) {
        return (msg_id === '15') ? message : undefined;
    };

    var counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 1);
    assert.equal(counts.stream_count.get(stream_id), 1);
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
        stream_id: 555,
        subject: 'phantom',
    };

    stream_data.get_sub_by_id = function () { return; };

    unread.process_read_message(message);
    var counts = unread.get_counts();
    assert.equal(counts.home_unread_messages, 0);
}());

(function test_private_messages() {
    narrow_state.active = function () {
        return false;
    };
    stream_data.is_subscribed = function () {
        return true;
    };

    var counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);

    var anybody = {
        email: 'anybody@example.com',
        user_id: 999,
        full_name: 'Any Body',
    };
    people.add_in_realm(anybody);

    var message = {
        id: 15,
        type: 'private',
        display_recipient: [
            {user_id: anybody.user_id},
            {id: me.user_id},
        ],
    };

    unread.process_loaded_messages([message]);

    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 1);
    assert.equal(counts.pm_count.get('999'), 1);
    unread.process_read_message(message);
    counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
    assert.equal(counts.pm_count.get('999'), 0);
}());

(function test_num_unread_for_person() {
    var alice = {
        email: 'alice@example.com',
        user_id: 101,
        full_name: 'Alice',
    };
    people.add_in_realm(alice);

    var bob = {
        email: 'bob@example.com',
        user_id: 102,
        full_name: 'Bob',
    };
    people.add_in_realm(bob);

    assert.equal(unread.num_unread_for_person(alice.user_id), 0);
    assert.equal(unread.num_unread_for_person(bob.user_id), 0);

    var message = {
        id: 15,
        display_recipient: [{id: alice.user_id}],
        type: 'private',
    };

    var read_message = {
        flags: ['read'],
    };
    unread.process_loaded_messages([message, read_message]);
    assert.equal(unread.num_unread_for_person(alice.user_id), 1);

    assert.equal(unread.num_unread_for_person(''), 0);
}());


(function test_mentions() {
    narrow_state.active = function () {
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
        stream_id: 999,
        subject: 'lunch',
        mentioned: true,
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
        id: 15,
    };
    current_msg_list.all_messages = function () {
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

(function test_errors() {
    global.blueslip.warn = function () {};

    // Test unknown message leads to zero count
    var message = {
        id: 9,
        type: 'private',
        display_recipient: [{id: 9999}],
    };

    unread.process_read_message(message);
    var counts = unread.get_counts();
    assert.equal(counts.private_message_count, 0);
}());


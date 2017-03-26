global.stub_out_jquery();

add_dependencies({
    people: 'js/people.js',
    util: 'js/util.js',
});

var noop = function () {};
var people = global.people;

set_global('alert_words', {
    process_message: noop,
});

var me = {
    email: 'me@example.com',
    user_id: 101,
    full_name: 'Me Myself',
};

var alice = {
    email: 'alice@example.com',
    user_id: 102,
    full_name: 'Alice',
};

var bob = {
    email: 'bob@example.com',
    user_id: 103,
    full_name: 'Bob',
};

var cindy = {
    email: 'cindy@example.com',
    user_id: 104,
    full_name: 'Cindy',
};

people.add_in_realm(me);
people.add_in_realm(alice);
people.add_in_realm(bob);
people.add_in_realm(cindy);

global.people.initialize_current_user(me.user_id);

global.util.execute_early = noop;

var message_store = require('js/message_store.js');

(function test_add_message_metadata() {
    var message = {
        sender_email: 'me@example.com',
        sender_id: me.user_id,
        type: 'private',
        display_recipient: [me, bob, cindy],
        flags: ['has_alert_word'],
    };
    message_store.add_message_metadata(message);

    assert.equal(message.is_private, true);
    assert.equal(message.reply_to, 'bob@example.com,cindy@example.com');
    assert.equal(message.to_user_ids, '103,104');
    assert.equal(message.display_reply_to, 'Bob, Cindy');
    assert.equal(message.alerted, true);
    assert.equal(message.is_me_message, false);
}());

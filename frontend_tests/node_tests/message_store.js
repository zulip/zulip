zrequire('pm_conversations');
zrequire('util');
zrequire('people');
zrequire('message_store');

var noop = function () {};
var people = global.people;

set_global('$', global.make_zjquery());
set_global('document', 'document-stub');

set_global('alert_words', {
    process_message: noop,
});

set_global('topic_data', {
    add_message: noop,
});

set_global('recent_senders', {
    process_message_for_senders: noop,
});

set_global('page_params', {
    realm_allow_message_editing: true,
    is_admin: true,
});

set_global('blueslip', global.make_zblueslip());

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

run_test('add_message_metadata', () => {
    var message = {
        sender_email: 'me@example.com',
        sender_id: me.user_id,
        type: 'private',
        display_recipient: [me, bob, cindy],
        flags: ['has_alert_word'],
        is_me_message: false,
        id: 2067,
    };
    message_store.set_message_booleans(message);
    message_store.add_message_metadata(message);

    assert.equal(message.is_private, true);
    assert.equal(message.reply_to, 'bob@example.com,cindy@example.com');
    assert.equal(message.to_user_ids, '103,104');
    assert.equal(message.display_reply_to, 'Bob, Cindy');
    assert.equal(message.alerted, true);
    assert.equal(message.is_me_message, false);

    var retrieved_message = message_store.get(2067);
    assert.equal(retrieved_message, message);

    // access cached previous message, and test match subject/content
    message = {
        id: 2067,
        match_subject: "topic foo",
        match_content: "bar content",
    };
    message = message_store.add_message_metadata(message);

    assert.equal(message.reply_to, 'bob@example.com,cindy@example.com');
    assert.equal(message.to_user_ids, '103,104');
    assert.equal(message.display_reply_to, 'Bob, Cindy');
    assert.equal(util.get_match_topic(message), 'topic foo');
    assert.equal(message.match_content, 'bar content');

    message = {
        sender_email: 'me@example.com',
        sender_id: me.user_id,
        type: 'stream',
        display_recipient: 'Zoolippy',
        topic: 'cool thing',
        subject: 'the_subject',
        id: 2068,
    };

    message_store.set_message_booleans(message);
    message_store.add_message_metadata(message);
    assert.deepEqual(message.stream, message.display_recipient);
    assert.equal(message.reply_to, 'me@example.com');
    assert.deepEqual(message.flags, undefined);
    assert.equal(message.alerted, false);
});

run_test('errors', () => {
    // Test a user that doesn't exist
    var message = {
        type: 'private',
        display_recipient: [{user_id: 92714}],
    };

    blueslip.set_test_data('error', 'Unknown user_id in get_person_from_user_id: 92714');
    blueslip.set_test_data('error', 'Unknown user id 92714'); // From person.js

    // Expect each to throw two blueslip errors
    // One from message_store.js, one from person.js
    var emails = message_store.get_pm_emails(message);
    assert.equal(emails, '?');
    assert.equal(blueslip.get_test_logs('error').length, 2);

    var names = message_store.get_pm_full_names(message);
    assert.equal(names, '?');
    assert.equal(blueslip.get_test_logs('error').length, 4);

    blueslip.clear_test_data();

    message = {
        type: 'stream',
        display_recipient: [{}],
    };

    // This should early return and not run pm_conversation.set_partner
    var num_partner = 0;
    set_global('pm_conversation', {
        set_partner: function () {
            num_partner += 1;
        },
    });
    message_store.process_message_for_recent_private_messages(message);
    assert.equal(num_partner, 0);
});

run_test('update_booleans', () => {
    var message = {};

    // First, test fields that we do actually want to update.
    message.mentioned = false;
    message.mentioned_me_directly = false;
    message.alerted = false;

    var flags = ['mentioned', 'has_alert_word', 'read'];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, true);
    assert.equal(message.mentioned_me_directly, true);
    assert.equal(message.alerted, true);

    flags = ['read'];
    message_store.update_booleans(message, flags);
    assert.equal(message.mentioned, false);
    assert.equal(message.mentioned_me_directly, false);
    assert.equal(message.alerted, false);

    // Make sure we don't muck with unread.
    message.unread = false;
    flags = [''];
    message_store.update_booleans(message, flags);
    assert.equal(message.unread, false);

    message.unread = true;
    flags = ['read'];
    message_store.update_booleans(message, flags);
    assert.equal(message.unread, true);
});

run_test('each', () => {
    message_store.each((message) => {
        assert(message.alerted !== undefined);
    });
});

run_test('message_id_change', () => {
    var message = {
        sender_email: 'me@example.com',
        sender_id: me.user_id,
        type: 'private',
        display_recipient: [me, bob, cindy],
        flags: ['has_alert_word'],
        id: 401,
    };
    message_store.add_message_metadata(message);

    set_global('pointer', {
        furthest_read: 401,
    });

    set_global('message_list', {});
    set_global('home_msg_list', {});

    var opts = {
        old_id: 401,
        new_id: 402,
    };

    global.with_stub(function (stub) {
        home_msg_list.change_message_id = stub.f;
        message_store.reify_message_id(opts);
        var msg_id = stub.get_args('old', 'new');
        assert.equal(msg_id.old, 401);
        assert.equal(msg_id.new, 402);
    });

    home_msg_list.view = {};
    global.with_stub(function (stub) {
        home_msg_list.view.change_message_id = stub.f;
        message_store.reify_message_id(opts);
        var msg_id = stub.get_args('old', 'new');
        assert.equal(msg_id.old, 401);
        assert.equal(msg_id.new, 402);
    });

});

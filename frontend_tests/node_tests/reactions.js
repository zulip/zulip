set_global('document', 'document-stub');
set_global('$', global.make_zjquery());

zrequire('people');
zrequire('reactions');

set_global('emoji', {
    emojis_by_name: {
        alien: '1f47d',
        smile: '1f604',
    },
    all_realm_emojis: {
        991: {
            id: '991',
            emoji_name: 'realm_emoji',
            emoji_url: 'TBD',
            deactivated: false,
        },
        992: {
            id: '992',
            emoji_name: 'inactive_realm_emoji',
            emoji_url: 'TBD',
            deactivated: true,
        },
        zulip: {
            id: 'zulip',
            emoji_name: 'zulip',
            emoji_url: 'TBD',
            deactivated: false,
        },
    },
    active_realm_emojis: {
        realm_emoji: {
            id: '991',
            emoji_name: 'realm_emoji',
            emoji_url: 'TBD',
        },
        zulip: {
            id: 'zulip',
            emoji_name: 'zulip',
            emoji_url: 'TBD',
        },
    },
    deactivated_realm_emojis: {
        inactive_realm_emoji: {
            emoji_name: 'inactive_realm_emoji',
            emoji_url: 'TBD',
        },
    },
});

set_global('blueslip', {
    warn: function () {},
});

set_global('page_params', {user_id: 5});

set_global('channel', {});
set_global('templates', {});
set_global('emoji_codes', {
    name_to_codepoint: {
        alien: '1f47d',
        smile: '1f604',
        frown: '1f626',
        octopus: '1f419',
    },
});
set_global('emoji_picker', {
    hide_emoji_popover: function () {},
});

var alice = {
    email: 'alice@example.com',
    user_id: 5,
    full_name: 'Alice',
};
var bob = {
    email: 'bob@example.com',
    user_id: 6,
    full_name: 'Bob van Roberts',
};
var cali = {
    email: 'cali@example.com',
    user_id: 7,
    full_name: 'Cali',
};
people.add_in_realm(alice);
people.add_in_realm(bob);
people.add_in_realm(cali);

var message = {
    id: 1001,
    reactions: [
        {emoji_name: 'smile', user: {id: 5}, reaction_type: 'unicode_emoji', emoji_code: '1f604'},
        {emoji_name: 'smile', user: {id: 6}, reaction_type: 'unicode_emoji', emoji_code: '1f604'},
        {emoji_name: 'frown', user: {id: 7}, reaction_type: 'unicode_emoji', emoji_code: '1f626'},
        {emoji_name: 'inactive_realm_emoji', user: {id: 5}, reaction_type: 'realm_emoji',
         emoji_code: '992'},

        // add some bogus user_ids
        {emoji_name: 'octopus', user: {id: 8888}, reaction_type: 'unicode_emoji', emoji_code: '1f419'},
        {emoji_name: 'frown', user: {id: 9999}, reaction_type: 'unicode_emoji', emoji_code: '1f626'},
    ],
};

set_global('message_store', {
    get: function (message_id) {
        assert.equal(message_id, 1001);
        return message;
    },
});

set_global('current_msg_list', {
    selected_message: function () {
        return { sent_by_me: true };
    },
    selected_row: function () {
        return $('.selected-row');
    },
    selected_id: function () {
        return 42;
    },
});

(function test_open_reactions_popover() {
    $('.selected-row').set_find_results('.actions_hover', $('.target-action'));
    $('.selected-row').set_find_results('.reaction_button', $('.target-reaction'));

    var called = false;
    emoji_picker.toggle_emoji_popover = function (target, id) {
        called = true;
        assert.equal(id, 42);
        assert.equal(target, $('.target-reaction')[0]);
    };

    assert(reactions.open_reactions_popover());
    assert(called);

    current_msg_list.selected_message = function () { return { sent_by_me: false }; };

    called = false;
    emoji_picker.toggle_emoji_popover = function (target, id) {
        called = true;
        assert.equal(id, 42);
        assert.equal(target, $('.target-action')[0]);
    };

    assert(reactions.open_reactions_popover());
    assert(called);
}());

(function test_basics() {
    var result = reactions.get_message_reactions(message);

    assert(reactions.current_user_has_reacted_to_emoji(message, '1f604', 'unicode_emoji'));
    assert(!reactions.current_user_has_reacted_to_emoji(message, '1f626', 'unicode_emoji'));

    result.sort(function (a, b) { return a.count - b.count; });

    var expected_result = [
      {
         emoji_name: 'frown',
         reaction_type: 'unicode_emoji',
         emoji_code: '1f626',
         local_id: 'unicode_emoji,frown,1f626',
         count: 1,
         user_ids: [7],
         title: 'Cali reacted with :frown:',
         emoji_alt_code: false,
         class: 'message_reaction',
      },
      {
         emoji_name: 'inactive_realm_emoji',
         reaction_type: 'realm_emoji',
         emoji_code: '992',
         local_id: 'realm_emoji,inactive_realm_emoji,992',
         count: 1,
         user_ids: [5],
         title: 'You (click to remove) reacted with :inactive_realm_emoji:',
         emoji_alt_code: false,
         is_realm_emoji: true,
         url: 'TBD',
         class: 'message_reaction reacted',
      },
      {
         emoji_name: 'smile',
         reaction_type: 'unicode_emoji',
         emoji_code: '1f604',
         local_id: 'unicode_emoji,smile,1f604',
         count: 2,
         user_ids: [5, 6],
         title: 'You (click to remove) and Bob van Roberts reacted with :smile:',
         emoji_alt_code: false,
         class: 'message_reaction reacted',
      },
   ];
   assert.deepEqual(result, expected_result);
}());

(function test_sending() {
    var message_id = 1001; // see above for setup
    var emoji_name = 'smile'; // should be a current reaction

    var orig_remove_reaction = reactions.remove_reaction;
    var orig_add_reaction = reactions.add_reaction;
    reactions.remove_reaction = function () {};
    reactions.add_reaction = function () {};

    global.with_stub(function (stub) {
        global.channel.del = stub.f;
        reactions.toggle_emoji_reaction(message_id, emoji_name);
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/reactions');
        assert.deepEqual(args.data, {
            reaction_type: 'unicode_emoji',
            emoji_name: 'smile',
            emoji_code: '1f604',
        });
        // args.success() does nothing; just make sure it doesn't crash
        args.success();

        // similarly, we only exercise the failure codepath
        global.channel.xhr_error_message = function () {};
        args.error();
    });

    emoji_name = 'alien'; // not set yet
    global.with_stub(function (stub) {
        global.channel.post = stub.f;
        reactions.toggle_emoji_reaction(message_id, emoji_name);
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/reactions');
        assert.deepEqual(args.data, {
            reaction_type: 'unicode_emoji',
            emoji_name: 'alien',
            emoji_code: '1f47d',
        });
    });

    emoji_name = 'inactive_realm_emoji';
    global.with_stub(function (stub) {
        // Test removing a deactivated realm emoji. An user can interact with a
        // deactivated realm emoji only by clicking on a reaction, hence, only
        // `process_reaction_click()` codepath supports deleting/adding a deactivated
        // realm emoji.
        global.channel.del = stub.f;
        reactions.process_reaction_click(message_id, 'realm_emoji,inactive_realm_emoji,992');
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/reactions');
        assert.deepEqual(args.data, {
            reaction_type: 'realm_emoji',
            emoji_name: 'inactive_realm_emoji',
            emoji_code: '992',
        });
    });

    emoji_name = 'zulip'; // Test adding zulip emoji.
    global.with_stub(function (stub) {
        global.channel.post = stub.f;
        reactions.toggle_emoji_reaction(message_id, emoji_name);
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/reactions');
        assert.deepEqual(args.data, {
            reaction_type: 'zulip_extra_emoji',
            emoji_name: 'zulip',
            emoji_code: 'zulip',
        });
    });

    var orig_func = global.blueslip.warn;
    var error_msg;
    global.blueslip.warn = function (msg) {
        error_msg = msg;
    };
    emoji_name = 'unknown-emoji';   // Test sending an emoji unknown to frontend.
    reactions.toggle_emoji_reaction(message_id, emoji_name);
    assert.equal(error_msg, 'Bad emoji name: ' + emoji_name);
    global.blueslip.warn = orig_func;
    reactions.add_reaction = orig_add_reaction;
    reactions.remove_reaction = orig_remove_reaction;
}());

(function test_set_reaction_count() {
    var count_element = $.create('count-stub');
    var reaction_element = $.create('reaction-stub');

    reaction_element.set_find_results('.message_reaction_count', count_element);

    reactions.set_reaction_count(reaction_element, 5);

    assert.equal(count_element.text(), '5');
}());

(function test_get_reaction_section() {
    var message_table = $.create('.message_table');
    var message_row = $.create('some-message-row');
    var message_reactions = $.create('our-reactions-section');

    message_table.set_find_results("[zid='555']", message_row);
    message_row.set_find_results('.message_reactions', message_reactions);

    var section = reactions.get_reaction_section(555);

    assert.equal(section, message_reactions);
}());

(function test_add_and_remove_reaction() {
    // Insert 8ball for Alice.
    var alice_event = {
        message_id: 1001,
        reaction_type: 'unicode_emoji',
        emoji_name: '8ball',
        emoji_code: '1f3b1',
        user: {
            user_id: alice.user_id,
        },
    };

    var message_reactions = $.create('our-reactions');

    reactions.get_reaction_section = function (message_id) {
        assert.equal(message_id, 1001);
        return message_reactions;
    };

    message_reactions.find = function (selector) {
        assert.equal(selector, '.reaction_button');
        return 'reaction-button-stub';
    };

    var template_called;
    global.templates.render = function (template_name, data) {
        template_called = true;
        assert.equal(template_name, 'message_reaction');
        assert.equal(data.class, 'message_reaction reacted');
        assert(!data.is_realm_emoji);
        assert.equal(data.message_id, 1001);
        assert.equal(data.title, 'You (click to remove) reacted with :8ball:');
        return '<new reaction html>';
    };

    var insert_called;
    $('<new reaction html>').insertBefore = function (element) {
        assert.equal(element, 'reaction-button-stub');
        insert_called = true;
    };

    reactions.add_reaction(alice_event);
    assert(template_called);
    assert(insert_called);

    // Running add_reaction again should not result in any changes
    template_called = false;
    insert_called = false;
    reactions.add_reaction(alice_event);
    assert(!template_called);
    assert(!insert_called);

    // Now, have Bob react to the same emoji (update).

    var bob_event = {
        message_id: 1001,
        reaction_type: 'unicode_emoji',
        emoji_name: '8ball',
        emoji_code: '1f3b1',
        user: {
            user_id: bob.user_id,
        },
    };

    var count_element = $.create('count-element');
    var reaction_element = $.create('reaction-element');
    reaction_element.set_find_results('.message_reaction_count', count_element);

    var title_set;
    reaction_element.prop = function (prop_name, value) {
        assert.equal(prop_name, 'title');
        var expected_msg = 'You (click to remove)' +
            ' and Bob van Roberts reacted with :8ball:';
        assert.equal(value, expected_msg);
        title_set = true;
    };

    message_reactions.find = function (selector) {
        assert.equal(selector, "[data-reaction-id='unicode_emoji,8ball,1f3b1']");
        return reaction_element;
    };

    reactions.add_reaction(bob_event);
    assert(title_set);
    assert.equal(count_element.text(), '2');

    // Now, remove Bob's 8ball emoji.  The event has the same exact
    // structure as the add event.
    title_set = false;
    reaction_element.prop = function (prop_name, value) {
        assert.equal(prop_name, 'title');
        var expected_msg = 'You (click to remove) reacted with :8ball:';
        assert.equal(value, expected_msg);
        title_set = true;
    };

    reactions.remove_reaction(bob_event);
    assert(title_set);
    assert.equal(count_element.text(), '1');

    var current_emojis = reactions.get_emojis_used_by_user_for_message_id(1001);
    assert.deepEqual(current_emojis, ['smile', 'inactive_realm_emoji', '8ball']);

    // Next, remove Alice's reaction, which exercises removing the
    // emoji icon.
    var removed;
    reaction_element.remove = function () {
        removed = true;
    };

    reactions.remove_reaction(alice_event);
    assert(removed);

    // Running remove_reaction again should not result in any changes
    removed = false;
    reactions.remove_reaction(alice_event);
    assert(!removed);

    current_emojis = reactions.get_emojis_used_by_user_for_message_id(1001);
    assert.deepEqual(current_emojis, ['smile', 'inactive_realm_emoji']);


    // Now add Cali's realm_emoji reaction.
    var cali_event = {
        message_id: 1001,
        reaction_type: 'realm_emoji',
        emoji_name: 'realm_emoji',
        emoji_code: '991',
        user: {
            user_id: cali.user_id,
        },
    };

    template_called = false;
    global.templates.render = function (template_name, data) {
        assert.equal(data.class, 'message_reaction');
        assert(data.is_realm_emoji);
        template_called = true;
        return '<new reaction html>';
    };

    message_reactions.find = function (selector) {
        assert.equal(selector, '.reaction_button');
        return 'reaction-button-stub';
    };

    reactions.add_reaction(cali_event);
    assert(template_called);
    assert(!reaction_element.hasClass('reacted'));

    // And then have Alice update it.
    alice_event = {
        message_id: 1001,
        reaction_type: 'realm_emoji',
        emoji_name: 'realm_emoji',
        emoji_code: '991',
        user: {
            user_id: alice.user_id,
        },
    };

    message_reactions.find = function (selector) {
        assert.equal(selector, "[data-reaction-id='realm_emoji,realm_emoji,991']");
        return reaction_element;
    };
    reaction_element.prop = function () {};
    reactions.add_reaction(alice_event);

    assert(reaction_element.hasClass('reacted'));
    var result = reactions.get_message_reactions(message);
    var realm_emoji_data = _.filter(result, function (v) {
        return v.emoji_name === 'realm_emoji';
    })[0];

    assert.equal(realm_emoji_data.count, 2);
    assert.equal(realm_emoji_data.is_realm_emoji, true);

    // And then remove Alice's reaction.
    reactions.remove_reaction(alice_event);
    assert(!reaction_element.hasClass('reacted'));

}());

(function test_with_view_stubs() {
    // This function tests reaction events by mocking out calls to
    // the view.

    var message = {
        id: 2001,
        reactions: [],
    };

    message_store.get = function () {
        return message;
    };

    function test_view_calls(test_params) {
        var calls = [];

        function add_call_func(name) {
            return function (opts) {
                calls.push({
                    name: name,
                    opts: opts,
                });
            };
        }

        reactions.view = {
            insert_new_reaction: add_call_func('insert_new_reaction'),
            update_existing_reaction: add_call_func('update_existing_reaction'),
            remove_reaction: add_call_func('remove_reaction'),
        };

        test_params.run_code();

        assert.deepEqual(calls, test_params.expected_view_calls);
    }

    var alice_8ball_event = {
        message_id: 2001,
        reaction_type: 'unicode_emoji',
        emoji_name: '8ball',
        emoji_code: '1f3b1',
        user: {
            user_id: alice.user_id,
        },
    };

    var bob_8ball_event = {
        message_id: 2001,
        reaction_type: 'unicode_emoji',
        emoji_name: '8ball',
        emoji_code: '1f3b1',
        user: {
            user_id: bob.user_id,
        },
    };

    var cali_airplane_event = {
        message_id: 2001,
        reaction_type: 'unicode_emoji',
        emoji_name: 'airplane',
        emoji_code: '2708',
        user: {
            user_id: cali.user_id,
        },
    };

    test_view_calls({
        run_code: function () {
            reactions.add_reaction(alice_8ball_event);
        },
        expected_view_calls: [
            {
                name: 'insert_new_reaction',
                opts: {
                    message_id: 2001,
                    reaction_type: 'unicode_emoji',
                    emoji_name: '8ball',
                    emoji_code: '1f3b1',
                    user_id: alice.user_id,
                },
            },
        ],
    });

    test_view_calls({
        run_code: function () {
            reactions.add_reaction(bob_8ball_event);
        },
        expected_view_calls: [
            {
                name: 'update_existing_reaction',
                opts: {
                    message_id: 2001,
                    reaction_type: 'unicode_emoji',
                    emoji_name: '8ball',
                    emoji_code: '1f3b1',
                    user_id: bob.user_id,
                    user_list: [alice.user_id, bob.user_id],
                },
            },
        ],
    });

    test_view_calls({
        run_code: function () {
            reactions.add_reaction(cali_airplane_event);
        },
        expected_view_calls: [
            {
                name: 'insert_new_reaction',
                opts: {
                    message_id: 2001,
                    reaction_type: 'unicode_emoji',
                    emoji_name: 'airplane',
                    emoji_code: '2708',
                    user_id: cali.user_id,
                },
            },
        ],
    });

    test_view_calls({
        run_code: function () {
            reactions.remove_reaction(bob_8ball_event);
        },
        expected_view_calls: [
            {
                name: 'remove_reaction',
                opts: {
                    message_id: 2001,
                    reaction_type: 'unicode_emoji',
                    emoji_name: '8ball',
                    emoji_code: '1f3b1',
                    user_id: bob.user_id,
                    user_list: [alice.user_id],
                },
            },
        ],
    });

    test_view_calls({
        run_code: function () {
            reactions.remove_reaction(alice_8ball_event);
        },
        expected_view_calls: [
            {
                name: 'remove_reaction',
                opts: {
                    message_id: 2001,
                    reaction_type: 'unicode_emoji',
                    emoji_name: '8ball',
                    emoji_code: '1f3b1',
                    user_id: alice.user_id,
                    user_list: [],
                },
            },
        ],
    });

}());

(function test_error_handling() {
    var error_msg;

    global.message_store.get = function () {
        return;
    };

    global.blueslip.error = function (msg) {
        error_msg = msg;
    };

    var bogus_event  = {
        message_id: 55,
        reaction_type: 'realm_emoji',
        emoji_name: 'realm_emoji',
        emoji_code: '991',
        user: {
            user_id: 99,
        },
    };

    var original_func = reactions.current_user_has_reacted_to_emoji;
    reactions.current_user_has_reacted_to_emoji = function () { return true; };
    reactions.toggle_emoji_reaction(55, bogus_event.emoji_name);
    assert.equal(error_msg, 'reactions: Bad message id: 55');
    reactions.current_user_has_reacted_to_emoji = original_func;

    error_msg = undefined;
    reactions.add_reaction(bogus_event);
    assert.equal(error_msg, undefined);

    reactions.remove_reaction(bogus_event);
    assert.equal(error_msg, undefined);
}());

(function test_local_reaction_id() {
    var reaction_info = {
        reaction_type: 'unicode_emoji',
        emoji_name: 'thumbs_up',
        emoji_code: '1f44d',
    };
    var local_id = reactions.get_local_reaction_id(reaction_info);
    assert.equal(local_id, 'unicode_emoji,thumbs_up,1f44d');

    var reverse_info = reactions.get_reaction_info(local_id);
    assert.deepEqual(reverse_info, reaction_info);
}());

(function test_process_reaction_click() {
    var message_id = 1001;
    var expected_reaction_info = {
        reaction_type: 'unicode_emoji',
        emoji_name: '8ball',
        emoji_code: '1f3b1',
    };
    global.message_store.get = function (message_id) {
        assert.equal(message_id, 1001);
        return message;
    };

    global.with_stub(function (stub) {
        global.channel.post = stub.f;
        reactions.process_reaction_click(message_id, 'unicode_emoji,8ball,1f3b1');
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/reactions');
        assert.deepEqual(args.data, expected_reaction_info);
    });

    expected_reaction_info = {
        reaction_type: 'unicode_emoji',
        emoji_name: 'smile',
        emoji_code: '1f604',
    };
    global.with_stub(function (stub) {
        global.channel.del = stub.f;
        reactions.process_reaction_click(message_id, 'unicode_emoji,smile,1f604');
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/reactions');
        assert.deepEqual(args.data, expected_reaction_info);
    });
}());

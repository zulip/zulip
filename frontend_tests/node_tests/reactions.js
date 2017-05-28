set_global('document', 'document-stub');
set_global('$', global.make_zjquery());

add_dependencies({
    people: 'js/people.js',
});

var reactions = require("js/reactions.js");

set_global('emoji', {
    emojis_name_to_css_class: {
        frown: 'frown-css',
        octopus: 'octopus-css',
        smile: 'smile-css',
    },
    emojis_by_name: {
        alien: '1f47d',
        smile: '1f604',
    },
    realm_emojis: {},
});

set_global('blueslip', {
    warn: function () {},
});

set_global('page_params', {user_id: 5});

set_global('channel', {});

(function make_people() {
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
}());

var message = {
    id: 1001,
    reactions: [
        {emoji_name: 'smile', user: {id: 5}},
        {emoji_name: 'smile', user: {id: 6}},
        {emoji_name: 'frown', user: {id: 7}},

        // add some bogus user_ids
        {emoji_name: 'octopus', user: {id: 8888}},
        {emoji_name: 'frown', user: {id: 9999}},
    ],
};

set_global('message_store', {
    get: function (message_id) {
        assert.equal(message_id, 1001);
        return message;
    },
});

(function test_basics() {
    var result = reactions.get_message_reactions(message);

    assert(reactions.current_user_has_reacted_to_emoji(message, 'smile'));
    assert(!reactions.current_user_has_reacted_to_emoji(message, 'frown'));

    result.sort(function (a, b) { return a.count - b.count; });

    var expected_result = [
      {
         emoji_name: 'frown',
         emoji_name_css_class: 'frown-css',
         count: 1,
         title: 'Cali reacted with :frown:',
         emoji_alt_code: undefined,
         class: 'message_reaction',
      },
      {
         emoji_name: 'smile',
         emoji_name_css_class: 'smile-css',
         count: 2,
         title: 'You (click to remove) and Bob van Roberts reacted with :smile:',
         emoji_alt_code: undefined,
         class: 'message_reaction reacted',
      },
   ];
   assert.deepEqual(result, expected_result);
}());

(function test_sending() {
    var message_id = 1001; // see above for setup
    var emoji_name = 'smile'; // should be a current reaction

    global.with_stub(function (stub) {
        global.channel.del = stub.f;
        reactions.message_reaction_on_click(message_id, emoji_name);
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/emoji_reactions/smile');

        // args.success() does nothing; just make sure it doesn't crash
        args.success();

        // similarly, we only exercise the failure codepath
        global.channel.xhr_error_message = function () {};
        args.error();
    });

    emoji_name = 'alien'; // not set yet
    global.with_stub(function (stub) {
        global.channel.put = stub.f;
        reactions.message_reaction_on_click(message_id, emoji_name);
        var args = stub.get_args('args').args;
        assert.equal(args.url, '/json/messages/1001/emoji_reactions/alien');
    });

    emoji_name = 'unknown-emoji';
    reactions.message_reaction_on_click(message_id, emoji_name);
}());

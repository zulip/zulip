set_global('document', {});
global.stub_out_jquery();

add_dependencies({
    people: 'js/people.js',
});

var reactions = require("js/reactions.js");

set_global('emoji', {
    emoji_name_to_css_class: function (name) {
        return name + '-css'; // only to make testing easy
    },
    realm_emojis: {},
});

set_global('blueslip', {
    warn: function () {},
});

set_global('page_params', {user_id: 1});

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

(function test_basics() {
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
    var result = reactions.get_message_reactions(message);

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
         title: 'Alice and Bob van Roberts reacted with :smile:',
         emoji_alt_code: undefined,
         class: 'message_reaction',
      },
   ];
   assert.deepEqual(result, expected_result);
}());

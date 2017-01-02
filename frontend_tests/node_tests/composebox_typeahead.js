var ct = require('js/composebox_typeahead.js');

var emoji_list = [{emoji_name: "tada", emoji_url: "TBD"},
                  {emoji_name: "moneybags", emoji_url: "TBD"}];
var stream_list = ['Denmark', 'Sweden'];

set_global('emoji', {emojis: emoji_list});
set_global('stream_data', {subscribed_subs: function () {
    return stream_list;
}});

global.stub_out_jquery();
add_dependencies({
    people: 'js/people.js',
});

global.people.add_in_realm({
    email: 'othello@zulip.com',
    user_id: 101,
    full_name: "Othello, Moor of Venice",
});
global.people.add_in_realm({
    email: 'cordelia@zulip.com',
    user_id: 102,
    full_name: "Cordelia Lear",
});

global.people.add({
    email: 'other@zulip.com',
    user_id: 103,
    full_name: "Deactivated User",
});

(function test_add_topic() {
    ct.add_topic('Denmark', 'civil fears');
    ct.add_topic('devel', 'fading');
    ct.add_topic('denmark', 'acceptance');
    ct.add_topic('denmark', 'Acceptance');
    ct.add_topic('Denmark', 'With Twisted Metal');

    assert.deepEqual(ct.topics_seen_for('Denmark'), ['With Twisted Metal', 'acceptance', 'civil fears']);
}());

(function test_begins_typeahead() {
    // Stub out split_at_cursor that uses $(':focus')
    ct.split_at_cursor = function (word) { return [word, '']; };

    var begin_typehead_this = {options: {completions: {
        emoji: true, mention: true, stream: true}}};

    function assert_typeahead_equals(input, reference) {
        var returned = ct.compose_content_begins_typeahead.call(begin_typehead_this, input);
        assert.deepEqual(returned, reference);
    }

    assert_typeahead_equals("test", false);
    assert_typeahead_equals("test one two", false);
    assert_typeahead_equals("test *", false);
    assert_typeahead_equals("test @", false);
    assert_typeahead_equals("test no@o", false);
    assert_typeahead_equals("test :-P", false);

    var all_items = [{ special_item_text: 'all (Notify everyone)', email: 'all', pm_recipient_count: Infinity, full_name: 'all' },
                     { special_item_text: 'everyone (Notify everyone)', email: 'everyone', full_name: 'everyone' }];
    var people_with_all = global.people.get_realm_persons().concat(all_items);

    assert_typeahead_equals("test @o", people_with_all);
    assert_typeahead_equals("test @z", people_with_all);
    assert_typeahead_equals("@zuli", people_with_all);

    assert_typeahead_equals("hi emoji :", false);
    assert_typeahead_equals("hi emoji :ta", emoji_list);
    assert_typeahead_equals("hi emoji :da", emoji_list);

    assert_typeahead_equals("test #", false);
    assert_typeahead_equals("test #D", stream_list);
    assert_typeahead_equals("#s", stream_list);
}());

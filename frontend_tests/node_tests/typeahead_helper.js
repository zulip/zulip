var th = require('js/typeahead_helper.js');

global.stub_out_jquery();

set_global('compose', {});
set_global('page_params', {is_zephyr_mirror_realm: false});

add_dependencies({
    stream_data: 'js/stream_data.js',
    people: 'js/people.js',
});

stream_data.create_streams([
    {name: 'Dev', subscribed: true, color: 'blue', stream_id: 1},
    {name: 'Linux', subscribed: true, color: 'red', stream_id: 2}
]);

var matches = [
    {
        email: "a_bot@zulip.com",
        full_name: "A zulip test bot",
        is_admin: false,
        is_bot: true,
        user_id: 1,
    }, {
        email: "a_user@zulip.org",
        full_name: "A zulip user",
        is_admin: false,
        is_bot: false,
        user_id: 2,
    }, {
        email: "b_user_1@zulip.net",
        full_name: "Bob 1",
        is_admin: false,
        is_bot: false,
        user_id: 3,
    }, {
        email: "b_user_2@zulip.net",
        full_name: "Bob 2",
        is_admin: true,
        is_bot: false,
        user_id: 4,
    }, {
        email: "b_bot@example.com",
        full_name: "B bot",
        is_admin: false,
        is_bot: true,
        user_id: 5,
    }, {
        email: "zman@test.net",
        full_name: "Zman",
        is_admin: false,
        is_bot: false,
        user_id: 6,
    }
];

_.each(matches, function (person) {
    global.people.add_in_realm(person);
});

(function test_sort_recipients() {
    function get_typeahead_result(query) {
        var result = th.sort_recipients(global.people.get_realm_persons(), query);
        return _.map(result, function (person) {
            return person.email;
        });
    }

    global.compose.stream_name = function () { return ""; };
    assert.deepEqual(get_typeahead_result("b"), [
        'b_user_1@zulip.net',
        'b_user_2@zulip.net',
        'b_bot@example.com',
        'a_user@zulip.org',
        'zman@test.net',
        'a_bot@zulip.com'
     ]);

    global.compose.stream_name = function () { return "Dev"; };
    var subscriber_email = "b_user_2@zulip.net";
    stream_data.add_subscriber("Dev", people.get_user_id(subscriber_email));
    assert.deepEqual(get_typeahead_result("b"), [
        subscriber_email,
        'b_user_1@zulip.net',
        'b_bot@example.com',
        'a_user@zulip.org',
        'zman@test.net',
        'a_bot@zulip.com'
    ]);

    // No match
    global.compose.stream_name = function () { return "Linux"; };
    assert.deepEqual(get_typeahead_result("h"), [
        'a_user@zulip.org',
        'b_user_1@zulip.net',
        'b_user_2@zulip.net',
        'zman@test.net',
        'a_bot@zulip.com',
        'b_bot@example.com'
    ]);

}());

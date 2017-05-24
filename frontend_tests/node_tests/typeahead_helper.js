var th = require('js/typeahead_helper.js');

set_global('page_params', {realm_is_zephyr_mirror_realm: false});

add_dependencies({
    stream_data: 'js/stream_data.js',
    people: 'js/people.js',
    typeahead_helper: 'js/typeahead_helper.js',
    util: 'js/util.js',
});

var popular = {num_items: function () {
    return 10;
}};

var unpopular = {num_items: function () {
    return 2;
}};

var test_streams = [
    {name: 'Dev', pin_to_top: false, subscribers: unpopular},
    {name: 'Docs', pin_to_top: false, subscribers: popular},
    {name: 'Derp', pin_to_top: false, subscribers: unpopular},
    {name: 'Denmark', pin_to_top: true, subscribers: popular},
    {name: 'dead', pin_to_top: false, subscribers: unpopular},
];

stream_data.create_streams([
    {name: 'Dev', subscribed: true, color: 'blue', stream_id: 1},
    {name: 'Linux', subscribed: true, color: 'red', stream_id: 2},
]);

global.stream_data.is_active = function (sub) {
    return sub.name !== 'dead';
};

test_streams = typeahead_helper.sort_streams(test_streams, 'd');
assert.deepEqual(test_streams[0].name, "Denmark"); // Pinned streams first
assert.deepEqual(test_streams[1].name, "Docs"); // Active streams next
assert.deepEqual(test_streams[2].name, "Derp"); // Less subscribers
assert.deepEqual(test_streams[3].name, "Dev"); // Alphabetically last
assert.deepEqual(test_streams[4].name, "dead"); // Inactive streams last

set_global('pygments_data', {langs:
    {python: 40, javscript: 50, php: 38, pascal: 29, perl: 22, css: 0},
});

var test_langs = ["pascal", "perl", "php", "python", "javascript"];
test_langs = typeahead_helper.sort_languages(test_langs, "p");

// Sort languages by matching first letter, and then by popularity
assert.deepEqual(test_langs, ["python", "php", "pascal", "perl", "javascript"]);

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
    },
];

_.each(matches, function (person) {
    global.people.add_in_realm(person);
});

(function test_sort_recipients() {
    function get_typeahead_result(query, current_stream) {
        var result = th.sort_recipients(
            global.people.get_realm_persons(),
            query,
            current_stream
        );
        return _.map(result, function (person) {
            return person.email;
        });
    }

    assert.deepEqual(get_typeahead_result("b", ""), [
        'b_user_1@zulip.net',
        'b_user_2@zulip.net',
        'b_bot@example.com',
        'a_user@zulip.org',
        'zman@test.net',
        'a_bot@zulip.com',
     ]);

    var subscriber_email = "b_user_2@zulip.net";
    stream_data.add_subscriber("Dev", people.get_user_id(subscriber_email));
    assert.deepEqual(get_typeahead_result("b", "Dev"), [
        subscriber_email,
        'b_user_1@zulip.net',
        'b_bot@example.com',
        'a_user@zulip.org',
        'zman@test.net',
        'a_bot@zulip.com',
    ]);

    // No match
    assert.deepEqual(get_typeahead_result("h", "Linux"), [
        'a_user@zulip.org',
        'b_user_1@zulip.net',
        'b_user_2@zulip.net',
        'zman@test.net',
        'a_bot@zulip.com',
        'b_bot@example.com',
    ]);

}());

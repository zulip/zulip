set_global('page_params', {realm_is_zephyr_mirror_realm: false});
set_global('templates', {});
set_global('md5', function (s) {
    return 'md5-' + s;
});

zrequire('Handlebars', 'handlebars');
zrequire('recent_senders');
zrequire('pm_conversations');
zrequire('people');
zrequire('emoji');
zrequire('util');
zrequire('stream_data');
zrequire('narrow');
zrequire('hash_util');
zrequire('marked', 'third/marked/lib/marked');
var th = zrequire('typeahead_helper');

stream_data.create_streams([
    {name: 'Dev', subscribed: true, color: 'blue', stream_id: 1},
    {name: 'Linux', subscribed: true, color: 'red', stream_id: 2},
]);

run_test('sort_streams', () => {
    var popular = {num_items: function () {
        return 10;
    }};

    var unpopular = {num_items: function () {
        return 2;
    }};

    var test_streams = [
        {name: 'Dev', pin_to_top: false, subscribers: unpopular, subscribed: true},
        {name: 'Docs', pin_to_top: false, subscribers: popular, subscribed: true},
        {name: 'Derp', pin_to_top: false, subscribers: unpopular, subscribed: true},
        {name: 'Denmark', pin_to_top: true, subscribers: popular, subscribed: true},
        {name: 'dead', pin_to_top: false, subscribers: unpopular, subscribed: true},
    ];
    _.each(test_streams, stream_data.update_calculated_fields);

    global.stream_data.is_active = function (sub) {
        return sub.name !== 'dead';
    };

    test_streams = th.sort_streams(test_streams, 'd');
    assert.deepEqual(test_streams[0].name, "Denmark"); // Pinned streams first
    assert.deepEqual(test_streams[1].name, "Docs"); // Active streams next
    assert.deepEqual(test_streams[2].name, "Derp"); // Less subscribers
    assert.deepEqual(test_streams[3].name, "Dev"); // Alphabetically last
    assert.deepEqual(test_streams[4].name, "dead"); // Inactive streams last

    // Test sort streams with description
    test_streams = [
        {name: 'Dev', description: 'development help', subscribers: unpopular, subscribed: true},
        {name: 'Docs', description: 'writing docs', subscribers: popular, subscribed: true},
        {name: 'Derp', description: 'derping around', subscribers: unpopular, subscribed: true},
        {name: 'Denmark', description: 'visiting Denmark', subscribers: popular, subscribed: true},
        {name: 'dead', description: 'dead stream', subscribers: unpopular, subscribed: true},
    ];
    _.each(test_streams, stream_data.update_calculated_fields);
    test_streams = th.sort_streams(test_streams, 'wr');
    assert.deepEqual(test_streams[0].name, "Docs"); // Description match
    assert.deepEqual(test_streams[1].name, "Denmark"); // Popular stream
    assert.deepEqual(test_streams[2].name, "Derp"); // Less subscribers
    assert.deepEqual(test_streams[3].name, "Dev"); // Alphabetically last
    assert.deepEqual(test_streams[4].name, "dead"); // Inactive streams last

    // Test sort both subscribed and unsubscribed streams.
    test_streams = [
        {name: 'Dev', description: 'Some devs', subscribed: true, subscribers: popular},
        {name: 'East', description: 'Developing east', subscribed: true, subscribers: popular},
        {name: 'New', description: 'No match', subscribed: true, subscribers: popular},
        {name: 'Derp', description: 'Always Derping', subscribed: false, subscribers: popular},
        {name: 'Ether', description: 'Destroying ether', subscribed: false, subscribers: popular},
        {name: 'Mew', description: 'Cat mews', subscribed: false, subscribers: popular},
    ];
    _.each(test_streams, stream_data.update_calculated_fields);

    test_streams = th.sort_streams(test_streams, 'd');
    assert.deepEqual(test_streams[0].name, "Dev"); // Subscribed and stream name starts with query
    assert.deepEqual(test_streams[1].name, "Derp"); // Unsubscribed and stream name starts with query
    assert.deepEqual(test_streams[2].name, "East"); // Subscribed and description starts with query
    assert.deepEqual(test_streams[3].name, "Ether"); // Unsubscribed and description starts with query
    assert.deepEqual(test_streams[4].name, "New"); // Subscribed and no match
    assert.deepEqual(test_streams[5].name, "Mew"); // Unsubscribed and no match
});

run_test('sort_languages', () => {
    set_global('pygments_data', {langs:
        {python: 40, javscript: 50, php: 38, pascal: 29, perl: 22, css: 0},
    });

    var test_langs = ["pascal", "perl", "php", "python", "javascript"];
    test_langs = th.sort_languages(test_langs, "p");

    // Sort languages by matching first letter, and then by popularity
    assert.deepEqual(test_langs, ["python", "php", "pascal", "perl", "javascript"]);

    // Test if popularity between two languages are the same
    global.pygments_data.langs.php = 40;
    test_langs = ["pascal", "perl", "php", "python", "javascript"];
    test_langs = th.sort_languages(test_langs, "p");

    assert.deepEqual(test_langs, ["php", "python", "pascal", "perl", "javascript"]);
});

var matches = [
    {
        email: "a_bot@zulip.com",
        full_name: "A bot",
        is_admin: false,
        is_bot: true,
        user_id: 1,
    }, {
        email: "a_user_1@zulip.org",
        full_name: "Alice 1",
        is_admin: false,
        is_bot: false,
        user_id: 2,
    }, {
        email: "a_user_2@zulip.org",
        full_name: "Bob 1",
        is_admin: false,
        is_bot: false,
        user_id: 3,
    }, {
        email: "b_user_1@zulip.net",
        full_name: "Alice 2",
        is_admin: false,
        is_bot: false,
        user_id: 4,
    }, {
        email: "b_user_2@zulip.net",
        full_name: "Bob 2",
        is_admin: true,
        is_bot: false,
        user_id: 5,
    }, {
        email: "b_user_3@zulip.net",
        full_name: "Bob 3",
        is_admin: false,
        is_bot: false,
        user_id: 6,
    }, {
        email: "b_bot@example.com",
        full_name: "B bot",
        is_admin: false,
        is_bot: true,
        user_id: 7,
    }, {
        email: "zman@test.net",
        full_name: "Zman",
        is_admin: false,
        is_bot: false,
        user_id: 8,
    },
];

_.each(matches, function (person) {
    global.people.add_in_realm(person);
});

run_test('sort_recipients', () => {
    function get_typeahead_result(query, current_stream, current_topic) {
        var result = th.sort_recipients(
            global.people.get_realm_persons(),
            query,
            current_stream,
            current_topic
        );
        return _.map(result, function (person) {
            return person.email;
        });
    }

    // Typeahead for recipientbox [query, "", undefined]
    assert.deepEqual(get_typeahead_result("b", ""), [
        'b_user_1@zulip.net',  // Match: email, alpha sort.
        'a_user_2@zulip.org',  // Match: name, alpha sort.
        'b_user_2@zulip.net',  // Match: name & email, alpha sort.
        'b_user_3@zulip.net',  // Match: name & email, alpha sort.
        'b_bot@example.com',   // Match: name & email, bot.
        'a_user_1@zulip.org',  // No match, alpha sort.
        'zman@test.net',       // No match, alpha sort.
        'a_bot@zulip.com',     // No match, bot.
    ]);

    // Typeahead for private message [query, "", ""]
    assert.deepEqual(get_typeahead_result("a", "", ""), [
        'a_user_1@zulip.org',  // Match: name & email, alpha sort.
        'b_user_1@zulip.net',  // Match: name, alpha sort.
        'a_user_2@zulip.org',  // Match: email, alpha sort.
        'a_bot@zulip.com',     // Match: name & email, bot.
        'b_user_2@zulip.net',  // No match, alpha sort.
        'b_user_3@zulip.net',  // No match, alpha sort.
        'zman@test.net',       // No match, alpha sort.
        'b_bot@example.com',   // No match, bot.
    ]);

    // For splitting based on subscription
    var subscriber_email_1 = "b_user_2@zulip.net";
    var subscriber_email_2 = "b_user_3@zulip.net";
    var subscriber_email_3 = "b_bot@example.com";
    stream_data.add_subscriber("Dev", people.get_user_id(subscriber_email_1));
    stream_data.add_subscriber("Dev", people.get_user_id(subscriber_email_2));
    stream_data.add_subscriber("Dev", people.get_user_id(subscriber_email_3));

    var dev_sub = stream_data.get_sub("Dev");
    stream_data.update_calculated_fields(dev_sub);

    // For spliting based on whether a PM was sent
    global.pm_conversations.set_partner(6);  // b_user_3@zulip.net
    global.pm_conversations.set_partner(7);  // b_bot@example.com
    global.pm_conversations.set_partner(2);  // a_user_1@zulip.org
    global.pm_conversations.set_partner(8);  // zman@test.net

    // For splitting based on recency
    global.recent_senders.process_message_for_senders({
        sender_id : 8,  // zman@test.net
        stream_id : 1,
        subject : "Dev Topic",
        id : _.uniqueId(),
    });
    global.recent_senders.process_message_for_senders({
        sender_id : 6,  // b_user_3@zulip.net
        stream_id : 1,
        subject : "Dev Topic",
        id : _.uniqueId(),
    });
    global.recent_senders.process_message_for_senders({
        sender_id : 7,  // b_bot@example.com
        stream_id : 1,
        subject : "Dev Topic",
        id : _.uniqueId(),
    });

    // Typeahead for stream message [query, stream-name, topic-name]
    assert.deepEqual(get_typeahead_result("b", "Dev", "Dev Topic"), [
        subscriber_email_3,    // Match: name & email, subscriber, PM partner, more recent sender.
        subscriber_email_2,    // Match: name & email, subscriber, PM partner, less recent sender.
        subscriber_email_1,    // Match: name & email, subscriber.
        'a_user_2@zulip.org',  // Match: name.
        'b_user_1@zulip.net',  // Match: email.
        'zman@test.net',       // No match, PM partner, recent sender.
        'a_user_1@zulip.org',  // No match, PM partner.
        'a_bot@zulip.com',     // No match.
    ]);

    // For splitting based on recency
    global.recent_senders.process_message_for_senders({
        sender_id : 6,  // b_user_3@zulip.net
        stream_id : 2,
        subject : "Linux Topic",
        id : _.uniqueId(),
    });
    global.recent_senders.process_message_for_senders({
        sender_id : 8,  // zman@test.net
        stream_id : 2,
        subject : "Linux Topic",
        id : _.uniqueId(),
    });

    // Typeahead for stream message: no match.
    assert.deepEqual(get_typeahead_result("h", "Linux", "Linux Topic"), [
        'zman@test.net',       // No match, PM partner, more recent sender.
        'b_user_3@zulip.net',  // No match, PM partner, less recent sender.
        'a_user_1@zulip.org',  // No match, PM partner.
        'b_bot@example.com',   // No match, PM partner.
        'a_bot@zulip.com',     // No match.
        'a_user_2@zulip.org',  // No match.
        'b_user_1@zulip.net',  // No match.
        'b_user_2@zulip.net',  // No match.
    ]);

    // Typeahead for stream message: "all" goes first.
    var person = {
        email: "all",
        full_name: "All",
        is_admin: false,
        is_bot: false,
        user_id: 42,
    };
    people.add_in_realm(person);

    assert.deepEqual(get_typeahead_result("a", "Linux", "Linux Topic"), [
        'all',
        'a_user_1@zulip.org',  // Match: name & email, PM partner.
        'a_bot@zulip.com',     // Match: name & email.
        'b_user_1@zulip.net',  // Match: name.
        'a_user_2@zulip.org',  // Match: email.
        'zman@test.net',       // No match, PM partner, more recent sender.
        'b_user_3@zulip.net',  // No match, PM partner, less recent sender.
        'b_bot@example.com',   // No match, PM partner.
        'b_user_2@zulip.net',  // No match.
    ]);

    people.deactivate(person);

    // For splitting based on PM counts
    matches[0].pm_recipient_count = 50;  // a_bot@zulip.com
    matches[1].pm_recipient_count = 2;   // a_user_1@zulip.org
    matches[3].pm_recipient_count = 32;  // b_user_1@zulip.net
    matches[4].pm_recipient_count = 42;  // b_user_2@zulip.net
    matches[5].pm_recipient_count = 0;   // b_user_3@zulip.net
    matches[6].pm_recipient_count = 1;   // b_bot@example.com

    // Typeahead for stream message: PM counts have no effect.
    assert.deepEqual(get_typeahead_result("b", "Linux", "Linux Topic"), [
        'b_user_3@zulip.net',  // Match: name & email, PM partner, recent sender.
        'b_bot@example.com',   // Match: name & email, PM partner.
        'a_user_2@zulip.org',  // Match: name.
        'b_user_2@zulip.net',  // Match: name & email.
        'b_user_1@zulip.net',  // Match: email.
        'zman@test.net',       // No match, PM partner, recent sender.
        'a_user_1@zulip.org',  // No match, PM partner.
        'a_bot@zulip.com',     // No match.
    ]);

    // Typeahead for private message: duplicates, PM counts.
    matches.push(matches[0]);

    var recipients = th.sort_recipients(matches, "b", "", "");
    var recipients_email = _.map(recipients, function (person) {
        return person.email;
    });
    var expected = [
        'b_bot@example.com',   // Match: name & email, PM partner, 1 PM.
        'b_user_3@zulip.net',  // Match: name & email, PM partner, 0 PMs.
        'b_user_2@zulip.net',  // Match: name & email, 42 PMs.
        'b_user_1@zulip.net',  // Match: email, 32 PMs.
        'a_user_2@zulip.org',  // Match: name.
        'a_user_1@zulip.org',  // No match, PM partner, 2 PMs.
        'zman@test.net',       // No match, PM partner.
        'a_bot@zulip.com',     // No match.
        'a_bot@zulip.com',
    ];
    assert.deepEqual(recipients_email, expected);

    // Reset matches
    matches.splice(matches.length - 1, 1);

    // Typeahead for stream message: names are a match, emails are "all".
    var small_matches = [
        {
            email: "all",
            full_name: "All 1",
            is_admin: false,
            is_bot: false,
            user_id: 43,
        }, {
            email: "all",
            full_name: "All 2",
            is_admin: false,
            is_bot: false,
            user_id: 44,
        },
    ];

    recipients = th.sort_recipients(small_matches, "a", "Linux", "Linux Topic");
    recipients_email = _.map(recipients, function (person) {
        return person.email;
    });
    expected = [
        'all',
        'all',
    ];
    assert.deepEqual(recipients_email, expected);

    // Typeahead for stream message: one of the users is a subscriber.
    small_matches = [
        matches[4],  // b_user_2@zulip.net
        matches[3],  // b_user_1@zulip.net
    ];
    recipients = th.sort_recipients(small_matches, "b", "Dev", "Dev Topic");
    recipients_email = _.map(recipients, function (person) {
        return person.email;
    });
    expected = [
        'b_user_2@zulip.net',  // subscriber
        'b_user_1@zulip.net',
    ];
    assert.deepEqual(recipients_email, expected);

    // Typeahead for stream message: one of the users is a PM partner.
    small_matches = [
        matches[5],  // b_user_3@zulip.net
        matches[4],  // b_user_2@zulip.net
    ];
    recipients = th.sort_recipients(small_matches, "b", "Linux", "Linux Topic");
    recipients_email = _.map(recipients, function (person) {
        return person.email;
    });
    expected = [
        'b_user_3@zulip.net',  // PM partner
        'b_user_2@zulip.net',
    ];
    assert.deepEqual(recipients_email, expected);
});

run_test('highlight_with_escaping', () => {
    var item = "Denmark";
    var query = "Den";
    var expected = "<strong>Den</strong>mark";
    var result = th.highlight_with_escaping(query, item);
    assert.equal(result, expected);

    item = "w3IrD_naMe";
    query = "w3IrD_naMe";
    expected = "<strong>w3IrD_naMe</strong>";
    result = th.highlight_with_escaping(query, item);
    assert.equal(result, expected);

    item = "development help";
    query = "development h";
    expected = "<strong>development h</strong>elp";
    result = th.highlight_with_escaping(query, item);
    assert.equal(result, expected);
});

run_test('render_person', () => {
    // Test render_person with regular person
    var rendered = false;
    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.equal(args.primary, matches[1].full_name);
        assert.equal(args.secondary, matches[1].email);
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_person(matches[1]), 'typeahead-item-stub');
    assert(rendered);

    // Test render_person with special_item_text person
    var special_person = {
        email: "special@example.com",
        full_name: "Special person",
        is_admin: false,
        is_bot: false,
        user_id: 7,
        special_item_text: "special_text",
    };
    rendered = false;
    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.equal(args.primary, special_person.special_item_text);
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_person(special_person), 'typeahead-item-stub');
    assert(rendered);
});

run_test('clear_rendered_person', () => {
    var rendered = false;
    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.equal(args.primary, matches[5].full_name);
        assert.equal(args.secondary, matches[5].email);
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_person(matches[5]), 'typeahead-item-stub');
    assert(rendered);

    // Bot once rendered won't be rendered again until clear_rendered_person
    // function is called. clear_rendered_person is used to clear rendered
    // data once bot name is modified.
    rendered = false;
    assert.equal(th.render_person(matches[5]), 'typeahead-item-stub');
    assert.equal(rendered, false);

    // Here rendered will be true as it is being rendered again.
    th.clear_rendered_person(matches[5].user_id);
    assert.equal(th.render_person(matches[5]), 'typeahead-item-stub');
    assert(rendered);

});

run_test('render_stream', () => {
    // Test render_stream with short description
    var rendered = false;
    var stream = {
        description: 'This is a short description.',
        stream_id: 42,
        name: 'Short Description',
    };
    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.equal(args.primary, stream.name);
        assert.equal(args.secondary, stream.description);
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_stream(stream), 'typeahead-item-stub');
    assert(rendered);

    // Test render_stream with long description
    rendered = false;
    stream = {
        description: 'This is a very very very very very long description.',
        stream_id: 43,
        name: 'Long Description',
    };
    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.equal(args.primary, stream.name);
        var short_desc = stream.description.substring(0, 35);
        assert.equal(args.secondary, short_desc + "...");
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_stream(stream), 'typeahead-item-stub');
    assert(rendered);
});

run_test('render_emoji', () => {
    // Test render_emoji with normal emoji.
    var rendered = false;
    var test_emoji = {
        emoji_name: 'thumbs_up',
        codepoint: '1f44d',
    };
    emoji.active_realm_emojis = {
        realm_emoji: 'TBD',
    };

    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.deepEqual(args, {
            primary: 'thumbs up',
            codepoint: '1f44d',
            is_emoji: true,
            has_image: false,
            has_secondary: false,
        });
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_emoji(test_emoji), 'typeahead-item-stub');
    assert(rendered);

    // Test render_emoji with normal emoji.
    rendered = false;
    test_emoji = {
        emoji_name: 'realm_emoji',
        emoji_url: 'TBD',
    };

    global.templates.render = function (template_name, args) {
        assert.equal(template_name, 'typeahead_list_item');
        assert.deepEqual(args, {
            primary: 'realm emoji',
            img_src: 'TBD',
            is_emoji: true,
            has_image: true,
            has_secondary: false,
        });
        rendered = true;
        return 'typeahead-item-stub';
    };
    assert.equal(th.render_emoji(test_emoji), 'typeahead-item-stub');
    assert(rendered);
});

run_test('sort_emojis', () => {
    var emoji_list = [
        { emoji_name: '+1' },
        { emoji_name: 'thumbs_up' },
        { emoji_name: 'pig' },
        { emoji_name: 'thumbs_down' },
    ];
    assert.deepEqual(th.sort_emojis(emoji_list, 'thumbs'), [
        { emoji_name: 'thumbs_up' },
        { emoji_name: 'thumbs_down' },
        { emoji_name: '+1' },
        { emoji_name: 'pig' },
    ]);
});

run_test('sort_recipientbox_typeahead', () => {
    var recipients = th.sort_recipientbox_typeahead("b, a", matches, ""); // search "a"
    var recipients_email = _.map(recipients, function (person) {
        return person.email;
    });
    assert.deepEqual(recipients_email, [
        'a_user_1@zulip.org',  // matches "a"
        'a_bot@zulip.com',     // matches "a"
        'b_user_1@zulip.net',  // matches "a"
        'a_user_2@zulip.org',  // matches "a"
        'b_bot@example.com',
        'b_user_3@zulip.net',
        'zman@test.net',
        'b_user_2@zulip.net',
    ]);

    recipients = th.sort_recipientbox_typeahead("b, a, b", matches, ""); // search "b"
    recipients_email = _.map(recipients, function (person) {
        return person.email;
    });
    assert.deepEqual(recipients_email, [
        'b_bot@example.com',   // matches "b"
        'b_user_3@zulip.net',  // matches "b"
        'b_user_2@zulip.net',  // matches "b"
        'b_user_1@zulip.net',  // matches "b"
        'a_user_2@zulip.org',  // matches "b"
        'a_user_1@zulip.org',
        'zman@test.net',
        'a_bot@zulip.com',
    ]);
});

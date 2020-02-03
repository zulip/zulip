var common = require('../casper_lib/common.js');

common.start_and_log_in();

function get_stream_li(stream_name) {
    var stream_id = common.get_stream_id(stream_name);
    return '#stream_filters [data-stream-id="' + stream_id + '"]';
}

// We could use the messages sent by 02-site.js, but we want to
// make sure each test file can be run individually (which the
// 'run' script provides for).

casper.then(function () {
    casper.test.info('Sending messages');
});

common.then_send_many([
    { stream: 'Verona', subject: 'frontend test',
      content: 'test message A' },

    { stream: 'Verona', subject: 'frontend test',
      content: 'test message B' },

    { stream: 'Verona', subject: 'other subject',
      content: 'test message C' },

    { stream: 'Denmark', subject: 'frontend test',
      content: 'other message' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content: 'personal A' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content: 'personal B' },

    { recipient: 'cordelia@zulip.com',
      content: 'personal C' },

    { stream: 'Verona', subject: 'frontend test',
      content: 'test message D' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content: 'personal D' },

    { recipient: 'cordelia@zulip.com',
      content: 'personal E' },
]);


// Define the messages we expect to see when narrowed.

function expect_home() {
    casper.then(function () {
        casper.waitUntilVisible('#zhome', function () {
            common.expected_messages('zhome', [
                'Verona > frontend test',
                'You and Cordelia Lear, King Hamlet',
                'You and Cordelia Lear',
            ], [
                '<p>test message D</p>',
                '<p>personal D</p>',
                '<p>personal E</p>',
            ]);
        });
    });
}

function expect_stream() {
    casper.then(function () {
        casper.waitUntilVisible('#zfilt', function () {
            common.expected_messages('zfilt', [
                'Verona > frontend test',
                'Verona > other subject',
                'Verona > frontend test',
            ], [
                '<p>test message A</p>',
                '<p>test message B</p>',
                '<p>test message C</p>',
                '<p>test message D</p>',
            ]);
        });
    });
}

function expect_stream_subject() {
    casper.then(function () {
        casper.waitUntilVisible('#zfilt', function () {
            common.expected_messages('zfilt', [
                'Verona > frontend test',
            ], [
                '<p>test message A</p>',
                '<p>test message B</p>',
                '<p>test message D</p>',
            ]);

            casper.test.assertEquals(casper.fetchText('#left_bar_compose_stream_button_big'), 'New topic');
        });
    });
}

function expect_subject() {
    casper.then(function () {
        casper.waitUntilVisible('#zfilt', function () {
            common.expected_messages('zfilt', [
                'Verona > frontend test',
                'Denmark > frontend test',
                'Verona > frontend test',
            ], [
                '<p>test message A</p>',
                '<p>test message B</p>',
                '<p>other message</p>',
                '<p>test message D</p>',
            ]);
        });
    });
}

function expect_huddle() {
    casper.then(function () {
        casper.waitUntilVisible('#zfilt', function () {
            common.expected_messages('zfilt', [
                'You and Cordelia Lear, King Hamlet',
            ], [
                '<p>personal A</p>',
                '<p>personal B</p>',
                '<p>personal D</p>',
            ]);
        });
    });
}

function expect_1on1() {
    casper.then(function () {
        casper.waitUntilVisible('#zfilt', function () {
            common.expected_messages('zfilt', [
                'You and Cordelia Lear',
            ], [
                '<p>personal C</p>',
                '<p>personal E</p>',
            ]);
        });
    });
}

function expect_all_pm() {
    casper.then(function () {
        casper.waitUntilVisible('#zfilt', function () {
            common.expected_messages('zfilt', [
                'You and Cordelia Lear, King Hamlet',
                'You and Cordelia Lear',
            ], [
                '<p>personal A</p>',
                '<p>personal B</p>',
                '<p>personal C</p>',
                '<p>personal D</p>',
                '<p>personal E</p>',
            ]);

            casper.test.assertEquals(casper.fetchText('#left_bar_compose_stream_button_big'), 'New stream message');
        });
    });
}

function expect_non_existing_user() {
    casper.then(function () {
        casper.waitUntilVisible('#non_existing_user', function () {
            casper.test.info("Empty feed for non existing user visible.");
            var expected_message = "\n        This user does not exist!" +
                "\n    ";
            this.test.assertEquals(casper.fetchText('#non_existing_user'), expected_message);
        });
    });
}

function expect_non_existing_users() {
    casper.then(function () {
        casper.waitUntilVisible('#non_existing_users', function () {
            casper.test.info("Empty feed for non existing user visible.");
            var expected_message = "\n        One or more of these users do not exist!" +
                "\n    ";
            this.test.assertEquals(casper.fetchText('#non_existing_users'), expected_message);
        });
    });
}

function check_narrow_title(title) {
    return function () {
        // need to get title tag from HTML
        // test if it's equal to some string passed in to function
        casper.test.assertSelectorHasText('title', title, 'Got expected narrow title');
    };
}

function un_narrow() {
    casper.then(common.un_narrow);
    expect_home();
    casper.then(check_narrow_title('home - Zulip Dev - Zulip'));
}

function search_and_check(str, item, check, narrow_title) {
    common.select_item_via_typeahead('#search_query', str, item);
    check();
    casper.then(check_narrow_title(narrow_title));
    un_narrow();
}

function search_silent_user(str, item) {
    common.select_item_via_typeahead('#search_query', str, item);
    casper.then(function () {
        casper.waitUntilVisible('#silent_user', function () {
            casper.test.info("Empty feed for silent user visible.");
            var expected_message = "\n        You haven't received any messages sent by this user yet!" +
                                    "\n    ";
            this.test.assertEquals(casper.fetchText('#silent_user'), expected_message);
        });
    });
    un_narrow();
}

function search_non_existing_user(str, item) {
    common.select_item_via_typeahead('#search_query', str, item);
    expect_non_existing_user();
    un_narrow();
}

// Narrow by clicking links.

casper.then(function () {
    common.wait_for_receive(function () {
        casper.test.info('Narrowing by clicking stream');
        casper.click('*[title="Narrow to stream \\"Verona\\""]');
    });
});

expect_stream();

casper.then(check_narrow_title('Verona - Zulip Dev - Zulip'));

un_narrow();

expect_home();

casper.then(function () {
    casper.test.info('Narrowing by clicking subject');
    casper.click('*[title="Narrow to stream \\"Verona\\", topic \\"frontend test\\""]');
});

expect_stream_subject();

casper.then(check_narrow_title('frontend test - Zulip Dev - Zulip'));

casper.then(function () {
    // Un-narrow by clicking "Zulip"
    casper.test.info('Un-narrowing');
    casper.click('.brand');
});

expect_home();

casper.then(function () {
    casper.test.info('Narrowing by clicking personal');
    casper.click('*[title="Narrow to your private messages with Cordelia Lear, King Hamlet"]');
});

expect_huddle();

casper.then(check_narrow_title('Cordelia Lear, King Hamlet - Zulip Dev - Zulip'));

casper.then(function () {
    // Un-narrow by clicking "Zulip"
    casper.test.info('Un-narrowing');
    casper.click('.brand');
});

expect_home();

// Narrow by typing in search strings or operators.
// Test stream / recipient autocomplete in the search bar
search_and_check('Verona', 'Stream', expect_stream,
                 'Verona - Zulip Dev - Zulip');

search_and_check('Cordelia', 'Private', expect_1on1,
                 'Cordelia Lear - Zulip Dev - Zulip');

// Test operators
search_and_check('stream:Verona', '', expect_stream,
                 'Verona - Zulip Dev - Zulip');

search_and_check('stream:Verona subject:frontend+test', '', expect_stream_subject,
                 'frontend test - Zulip Dev - Zulip');

search_and_check('stream:Verona topic:frontend+test', '', expect_stream_subject,
                 'frontend test - Zulip Dev - Zulip');

search_and_check('subject:frontend+test', '', expect_subject,
                 'home - Zulip Dev - Zulip');

search_silent_user('sender:emailgateway@zulip.com', '');

search_non_existing_user('sender:dummyuser@zulip.com', '');

search_and_check('pm-with:dummyuser@zulip.com', '', expect_non_existing_user, 'Invalid user');

search_and_check('pm-with:dummyuser@zulip.com,dummyuser2@zulip.com', '', expect_non_existing_users,
                 'Invalid users');

// Narrow by clicking the left sidebar.
casper.then(function () {
    casper.test.info('Narrowing with left sidebar');
    casper.click(get_stream_li("Verona") + ' a');
});

expect_stream();

casper.then(check_narrow_title('Verona - Zulip Dev - Zulip'));

casper.thenClick('.top_left_all_messages a');

expect_home();

casper.then(check_narrow_title('home - Zulip Dev - Zulip'));

casper.thenClick('.top_left_private_messages a');

expect_all_pm();

casper.then(check_narrow_title('Private messages - Zulip Dev - Zulip'));

un_narrow();

// Make sure stream search filters the stream list
casper.then(function () {
    casper.test.info('Search streams using left sidebar');
    casper.test.assertExists('.input-append.notdisplayed', 'Stream filter box not visible initially');
    casper.click('#streams_header .sidebar-title');
});

casper.waitWhileSelector('#streams_list .input-append.notdisplayed', function () {
    casper.test.assertExists(get_stream_li("Denmark"),
                             'Original stream list contains Denmark');
    casper.test.assertExists(get_stream_li("Scotland"),
                             'Original stream list contains Scotland');
    casper.test.assertExists(get_stream_li("Verona"),
                             'Original stream list contains Verona');
});

// Enter the search box and test highlighted suggestion navigation
casper.then(function () {
    casper.evaluate(function () {
        $('.stream-list-filter').expectOne()
            .focus()
            .trigger($.Event('click'));
    });
});

casper.waitForSelector('#stream_filters .highlighted_stream', function () {
    casper.test.info('Suggestion highlighting - initial situation');
    casper.test.assertExist(get_stream_li("Denmark") + '.highlighted_stream',
                            'Stream Denmark is highlighted');
    casper.test.assertDoesntExist(get_stream_li("Scotland") + '.highlighted_stream',
                                  'Stream Scotland is not highlighted');
    casper.test.assertDoesntExist(get_stream_li("Verona") + '.highlighted_stream',
                                  'Stream Verona is not highlighted');
});

// Use arrow keys to navigate through suggestions
casper.then(function () {
    function arrow(key) {
        casper.sendKeys('.stream-list-filter',
                        casper.page.event.key[key],
                        {keepFocus: true});
    }
    arrow('Down'); // Denmark -> Scotland
    arrow('Up'); // Scotland -> Denmark
    arrow('Up'); // Denmark -> Denmark
    arrow('Down'); // Denmark -> Scotland
});

casper.then(function () {
    casper.waitForSelector(get_stream_li("Scotland") + '.highlighted_stream', function () {
        casper.test.info('Suggestion highlighting - after arrow key navigation');
        casper.test.assertDoesntExist(
            get_stream_li("Denmark") + '.highlighted_stream',
            'Stream Denmark is not highlighted');
        casper.test.assertExist(
            get_stream_li("Scotland") + '.highlighted_stream',
            'Stream Scotland is  highlighted');
        casper.test.assertDoesntExist(
            get_stream_li("Verona") + '.highlighted_stream',
            'Stream Verona is not highlighted');
    });
});

// We search for the beginning of "Scotland", not case sensitive
casper.then(function () {
    casper.evaluate(function () {
        $('.stream-list-filter').expectOne()
            .focus()
            .val('sCoT')
            .trigger($.Event('input'))
            .trigger($.Event('click'));
    });
});

// There will be no race condition between these two waits because we
// expect them to happen in parallel.
casper.waitWhileVisible(get_stream_li("Denmark"), function () {
    casper.test.info('Search term entered');
    casper.test.assertDoesntExist(get_stream_li("Denmark"),
                                  'Filtered stream list does not contain Denmark');
});
casper.waitWhileVisible(get_stream_li("Verona"), function () {
    casper.test.assertDoesntExist(get_stream_li("Verona"),
                                  'Filtered stream list does not contain Verona');
});

casper.then(function () {
    casper.test.assertExists(get_stream_li("Scotland"),
                             'Filtered stream list does contain Scotland');
    casper.test.assertExists(get_stream_li("Scotland") + '.highlighted_stream',
                             'Stream Scotland is highlighted');
});

// Clearing the list should give us back all the streams in the list
casper.then(function () {
    casper.evaluate(function () {
        $('.stream-list-filter').expectOne()
            .focus()
            .val('')
            .trigger($.Event('input'));
    });
});

casper.then(function () {
    casper.waitUntilVisible(get_stream_li("Denmark"), function () {
        casper.test.assertExists(get_stream_li("Denmark"),
                                 'Restored stream list contains Denmark');
    });
    casper.waitUntilVisible(get_stream_li("Scotland"), function () {
        casper.test.assertExists(get_stream_li("Denmark"),
                                 'Restored stream list contains Scotland');
    });
    casper.waitUntilVisible(get_stream_li("Verona"), function () {
        casper.test.assertExists(get_stream_li("Denmark"),
                                 'Restored stream list contains Verona');
    });
});


casper.thenClick('#streams_header .sidebar-title');

casper.waitForSelector('.input-append.notdisplayed', function () {
    casper.test.assertExists('.input-append.notdisplayed',
                             'Stream filter box not visible after second click');
});

// We search for the beginning of "Verona", not case sensitive
casper.then(function () {
    casper.evaluate(function () {
        $('.stream-list-filter').expectOne()
            .focus()
            .val('ver')
            .trigger($.Event('input'));
    });
});

casper.waitWhileVisible(get_stream_li("Denmark"), function () {
    // Clicking the narrowed list should clear the search
    casper.click(get_stream_li("Verona") + ' a');
    expect_stream();
    casper.test.assertEquals(casper.fetchText('.stream-list-filter'), '', 'Clicking on a stream clears the search');
});

un_narrow();

function assert_in_list(name) {
    casper.test.assertExists(
        '#user_presences li [data-name="' + name + '"]',
        'User ' + name + ' is IN buddy list'
    );
}

function assert_selected(name) {
    casper.test.assertExists(
        '#user_presences li.highlighted_user [data-name="' + name + '"]',
        'User ' + name + ' is SELECTED IN buddy list'
    );
}

function assert_not_selected(name) {
    assert_in_list(name);
    casper.test.assertDoesntExist(
        '#user_presences li.highlighted_user [data-name="' + name + '"]',
        'User ' + name + ' is NOT SELECTED buddy list'
    );
}


// User search at the right sidebar
casper.then(function () {
    casper.test.info('Search users using right sidebar');
    assert_in_list('Iago');
    assert_in_list('Cordelia Lear');
    assert_in_list('King Hamlet');
    assert_in_list('aaron');
});

// Enter the search box and test selected suggestion navigation
// Click on search icon
casper.then(function () {
    casper.evaluate(function () {
        $('#user_filter_icon').expectOne()
            .focus()
            .trigger($.Event('click'));
    });
});

casper.waitForSelector('#user_presences .highlighted_user', function () {
    casper.test.info('Suggestion highlighting - initial situation');
    assert_selected('Iago');
    assert_not_selected('Cordelia Lear');
    assert_not_selected('King Hamlet');
    assert_not_selected('aaron');
});

// Use arrow keys to navigate through suggestions
casper.then(function () {
    function arrow(key) {
        casper.sendKeys('.user-list-filter',
                        casper.page.event.key[key],
                        {keepFocus: true});
    }

    // go down 2, up 3 (which is really 2), then down 2
    //    Iago
    //    Cordelia
    //    Hamlet
    arrow('Down');
    arrow('Down');
    arrow('Up');
    arrow('Up');
    arrow('Up'); // does nothing
    arrow('Down');
    arrow('Down');
});

casper.waitForSelector('#user_presences li.highlighted_user [data-name="King Hamlet"]', function () {
    casper.test.info('Suggestion highlighting - after arrow key navigation');
    assert_not_selected('Iago');
    assert_not_selected('Cordelia Lear');
    assert_selected('King Hamlet');
});

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});

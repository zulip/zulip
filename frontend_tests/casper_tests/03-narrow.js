var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

// We could use the messages sent by 02-site.js, but we want to
// make sure each test file can be run individually (which the
// 'run' script provides for).

casper.then(function () {
    casper.test.info('Sending messages');
});

common.then_send_many([
    { stream:  'Verona', subject: 'frontend test',
      content: 'test message A' },

    { stream:  'Verona', subject: 'frontend test',
      content: 'test message B' },

    { stream:  'Verona', subject: 'other subject',
      content: 'test message C' },

    { stream:  'Denmark', subject: 'frontend test',
      content: 'other message' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content:   'personal A' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content:   'personal B' },

    { recipient: 'cordelia@zulip.com',
      content:   'personal C' },

    { stream:  'Verona', subject: 'frontend test',
      content: 'test message D' },

    { recipient: 'cordelia@zulip.com, hamlet@zulip.com',
      content:   'personal D' },

    { recipient: 'cordelia@zulip.com',
      content:   'personal E' },
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
            var expected_message = "\n        You haven't received any messages sent by this user yet!"+
                                    "\n    ";
            this.test.assertEquals(casper.fetchText('#silent_user'), expected_message);
        });
    });
    un_narrow();
}

function search_non_existing_user(str, item) {
    common.select_item_via_typeahead('#search_query', str, item);
    casper.then(function () {
        casper.waitUntilVisible('#non_existing_user', function () {
            casper.test.info("Empty feed for non existing user visible.");
            var expected_message = "\n        This user does not exist!"+
                                    "\n    ";
            this.test.assertEquals(casper.fetchText('#non_existing_user'), expected_message);
        });
    });
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
    // This time, un-narrow by hitting the search 'x'
    casper.test.info('Un-narrowing');
    casper.click('#search_exit');
});

expect_home();

casper.then(function () {
    casper.test.info('Narrowing by clicking personal');
    casper.click('*[title="Narrow to your private messages with Cordelia Lear, King Hamlet"]');
});

expect_huddle();

casper.then(check_narrow_title('private - Zulip Dev - Zulip'));

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
                 'private - Zulip Dev - Zulip');

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

// Narrow by clicking the left sidebar.
casper.then(function () {
    casper.test.info('Narrowing with left sidebar');
    casper.click('#stream_filters [data-stream-name="Verona"] a');
});

expect_stream();

casper.then(check_narrow_title('Verona - Zulip Dev - Zulip'));

casper.thenClick('#global_filters [data-name="home"] a');

expect_home();

casper.then(check_narrow_title('home - Zulip Dev - Zulip'));

casper.thenClick('#global_filters [data-name="private"] a');

expect_all_pm();

casper.then(check_narrow_title('private - Zulip Dev - Zulip'));

un_narrow();

// Make sure stream search filters the stream list
casper.then(function () {
    casper.test.info('Search streams using left sidebar');
    casper.test.assertExists('.input-append.notdisplayed', 'Stream filter box not visible initially');
    casper.click('#streams_header .sidebar-title');
});

casper.waitWhileSelector('#streams_list .input-append.notdisplayed', function () {
    casper.test.assertExists('#stream_filters [data-stream-name="Denmark"]',
                             'Original stream list contains Denmark');
    casper.test.assertExists('#stream_filters [data-stream-name="Scotland"]',
                             'Original stream list contains Scotland');
    casper.test.assertExists('#stream_filters [data-stream-name="Verona"]',
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
    casper.test.assertExist('#stream_filters [data-stream-name="Denmark"].highlighted_stream',
                            'Stream Denmark is highlighted');
    casper.test.assertDoesntExist('#stream_filters [data-stream-name="Scotland"].highlighted_stream',
                                  'Stream Scotland is not highlighted');
    casper.test.assertDoesntExist('#stream_filters [data-stream-name="Verona"].highlighted_stream',
                                  'Stream Verona is not highlighted');
});

// Use arrow keys to navigate through suggestions
casper.then(function () {
    // Down: Denmark -> Scotland
    casper.sendKeys('.stream-list-filter', casper.page.event.key.Down, {keepFocus: true});
    // Up: Scotland -> Denmark
    casper.sendKeys('.stream-list-filter', casper.page.event.key.Up, {keepFocus: true});
    // Up: Denmark -> Verona
    casper.sendKeys('.stream-list-filter', casper.page.event.key.Up, {keepFocus: true});
});

casper.waitForSelector('#stream_filters [data-stream-name="Verona"].highlighted_stream', function () {
    casper.test.info('Suggestion highlighting - after arrow key navigation');
    casper.test.assertDoesntExist('#stream_filters [data-stream-name="Denmark"].highlighted_stream',
                                  'Stream Denmark is not highlighted');
    casper.test.assertDoesntExist('#stream_filters [data-stream-name="Scotland"].highlighted_stream',
                                  'Stream Scotland is not highlighted');
    casper.test.assertExist('#stream_filters [data-stream-name="Verona"].highlighted_stream',
                            'Stream Verona is highlighted');
});

// We search for the beginning of "Verona", not case sensitive
casper.then(function () {
    casper.evaluate(function () {
        $('.stream-list-filter').expectOne()
            .focus()
            .val('ver')
            .trigger($.Event('input'))
            .trigger($.Event('click'));
    });
});

// There will be no race condition between these two waits because we
// expect them to happen in parallel.
casper.waitWhileVisible('#stream_filters [data-stream-name="Denmark"]', function () {
    casper.test.info('Search term entered');
    casper.test.assertDoesntExist('#stream_filters [data-stream-name="Denmark"]',
                                  'Filtered stream list does not contain Denmark');
});
casper.waitWhileVisible('#stream_filters [data-stream-name="Scotland"]', function () {
    casper.test.assertDoesntExist('#stream_filters [data-stream-name="Scotland"]',
                                  'Filtered stream list does not contain Scotland');
});

casper.then(function () {
    casper.test.assertExists('#stream_filters [data-stream-name="Verona"]',
                             'Filtered stream list does contain Verona');
    casper.test.assertExists('#stream_filters [data-stream-name="Verona"].highlighted_stream',
                             'Stream Verona is highlighted');
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

// There will be no race condition between these waits because we
// expect them to happen in parallel.
casper.waitUntilVisible('#stream_filters [data-stream-name="Denmark"]', function () {
    casper.test.assertExists('#stream_filters [data-stream-name="Denmark"]',
                             'Restored stream list contains Denmark');
});
casper.waitUntilVisible('#stream_filters [data-stream-name="Scotland"]', function () {
    casper.test.assertExists('#stream_filters [data-stream-name="Denmark"]',
                             'Restored stream list contains Scotland');
});
casper.waitUntilVisible('#stream_filters [data-stream-name="Verona"]', function () {
    casper.test.assertExists('#stream_filters [data-stream-name="Denmark"]',
                             'Restored stream list contains Verona');
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

casper.waitWhileVisible('#stream_filters [data-stream-name="Denmark"]', function () {
    // Clicking the narrowed list should clear the search
    casper.click('#stream_filters [data-stream-name="Verona"] a');
    expect_stream();
    casper.test.assertEquals(casper.fetchText('.stream-list-filter'), '', 'Clicking on a stream clears the search');
});

un_narrow();

// User search at the right sidebar
casper.then(function () {
    casper.test.info('Search users using right sidebar');
    casper.test.assertExists('#user_presences li [data-name="Cordelia Lear"]',
                             'User Cordelia Lear exists');
    casper.test.assertExists('#user_presences li [data-name="King Hamlet"]',
                             'User King Hamlet exists');
    casper.test.assertExists('#user_presences li [data-name="aaron"]',
                             'User aaron exists');
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
    casper.test.assertExist('#user_presences li.highlighted_user [data-name="Cordelia Lear"]',
                            'User Cordelia Lear is selected');
    casper.test.assertDoesntExist('#user_presences li.highlighted_user [data-name="King Hamlet"]',
                                  'User King Hamlet is not selected');
    casper.test.assertDoesntExist('#user_presences li.highlighted_user [data-name="aaron"]',
                                  'User aaron is not selected');
});

// Use arrow keys to navigate through suggestions
casper.then(function () {
    // Down: Cordelia -> Hamlet
    casper.sendKeys('.user-list-filter', casper.page.event.key.Down, {keepFocus: true});
    // Up: Hamlet -> Cordelia
    casper.sendKeys('.user-list-filter', casper.page.event.key.Up, {keepFocus: true});
    // Up: Cordelia -> aaron
    casper.sendKeys('.user-list-filter', casper.page.event.key.Up, {keepFocus: true});
});

casper.waitForSelector('#user_presences li.highlighted_user [data-name="aaron"]', function () {
    casper.test.info('Suggestion highlighting - after arrow key navigation');
    casper.test.assertDoesntExist('#user_presences li.highlighted_user [data-name="Cordelia Lear"]',
        'User Cordelia Lear not is selected');
    casper.test.assertDoesntExist('#user_presences li.highlighted_user [data-name="King Hamlet"]',
        'User King Hamlet is not selected');
    casper.test.assertExist('#user_presences li.highlighted_user [data-name="aaron"]',
        'User aaron is selected');
});

common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});

var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

// We could use the messages sent by 01-site.js, but we want to
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

    { stream:  'Venice', subject: 'frontend test',
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
      content:   'personal E' }
]);


// Define the messages we expect to see when narrowed.

function expect_home() {
    common.expected_messages('zhome', [
        'Verona > frontend test',
        'You and Cordelia Lear, King Hamlet',
        'You and Cordelia Lear'
    ], [
        '<p>test message D</p>',
        '<p>personal D</p>',
        '<p>personal E</p>'
    ]);
}

function expect_stream() {
    common.expected_messages('zfilt', [
        'Verona > frontend test',
        'Verona > other subject',
        'Verona > frontend test'
    ], [
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message C</p>',
        '<p>test message D</p>'
    ]);
}

function expect_stream_subject() {
    common.expected_messages('zfilt', [
        'Verona > frontend test'
    ], [
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>test message D</p>'
    ]);
}

function expect_subject() {
    common.expected_messages('zfilt', [
        'Verona > frontend test',
        'Venice > frontend test',
        'Verona > frontend test'
    ], [
        '<p>test message A</p>',
        '<p>test message B</p>',
        '<p>other message</p>',
        '<p>test message D</p>'
    ]);
}

function expect_huddle() {
    common.expected_messages('zfilt', [
        'You and Cordelia Lear, King Hamlet'
    ], [
        '<p>personal A</p>',
        '<p>personal B</p>',
        '<p>personal D</p>'
    ]);
}

function expect_1on1() {
    common.expected_messages('zfilt', [
        'You and Cordelia Lear'
    ], [
        '<p>personal C</p>',
        '<p>personal E</p>'
    ]);
}

function expect_all_pm() {
    common.expected_messages('zfilt', [
        'You and Cordelia Lear, King Hamlet',
        'You and Cordelia Lear'
    ], [
        '<p>personal A</p>',
        '<p>personal B</p>',
        '<p>personal C</p>',
        '<p>personal D</p>',
        '<p>personal E</p>'
    ]);
}

function un_narrow() {
    casper.then(common.un_narrow);
    casper.then(expect_home);
}


// Narrow by clicking links.

common.wait_for_receive(function () {
    casper.test.info('Narrowing by clicking stream');
    casper.click('*[title="Narrow to stream \\\"Verona\\\""]');
});

casper.waitUntilVisible('#zfilt', function () {
    expect_stream();
});
un_narrow();

casper.waitUntilVisible('#zhome', function () {
    expect_home();
    casper.test.info('Narrowing by clicking subject');
    casper.click('*[title="Narrow to stream \\\"Verona\\\", topic \\\"frontend test\\\""]');
});

casper.waitUntilVisible('#zfilt', function () {
    expect_stream_subject();

    // This time, un-narrow by hitting the search 'x'
    casper.test.info('Un-narrowing');
    casper.click('#search_exit');
});

casper.waitUntilVisible('#zhome', function () {
    expect_home();
    casper.test.info('Narrowing by clicking personal');
    casper.click('*[title="Narrow to your private messages with Cordelia Lear, King Hamlet"]');
});


casper.waitUntilVisible('#zfilt', function () {
    expect_huddle();

    // Un-narrow by clicking "Zulip"
    casper.test.info('Un-narrowing');
    casper.click('.brand');
});


// Narrow by typing in search strings or operators.

// Put the specified string into the search box, then
// select the menu item matching 'item'.
function do_search(str, item) {
    casper.then(function () {
        casper.test.info('Searching ' + str + ', ' + item);

        casper.evaluate(function (str, item) {
            // Set the value and then send a bogus keyup event to trigger
            // the typeahead.
            $('#search_query')
                .focus()
                .val(str)
                .trigger($.Event('keyup', { which: 0 }));

            // You might think these steps should be split by casper.then,
            // but apparently that's enough to make the typeahead close (??),
            // but not the first time you use do_search.

            // Trigger the typeahead.
            // Reaching into the guts of Bootstrap Typeahead like this is not
            // great, but I found it very hard to do it any other way.
            var tah = $('#search_query').data().typeahead;
            tah.mouseenter({
                currentTarget: $('.typeahead:visible li:contains("'+item+'")')[0]
            });
            tah.select();
        }, {str: str, item: item});
    });
}

function search_and_check(str, item, check) {
    do_search(str, item);

    casper.then(check);
    un_narrow();
}

casper.waitUntilVisible('#zhome', expect_home);

// Test stream / recipient autocomplete in the search bar
search_and_check('Verona',   'Narrow to stream',  expect_stream);
search_and_check('Cordelia', 'Narrow to private', expect_1on1);

// Test operators
search_and_check('stream:verona',                       'Narrow', expect_stream);
search_and_check('stream:verona subject:frontend+test', 'Narrow', expect_stream_subject);
search_and_check('subject:frontend+test',               'Narrow', expect_subject);


// Narrow by clicking the left sidebar.
casper.then(function () {
    casper.test.info('Narrowing with left sidebar');
});
casper.thenClick('#stream_filters [data-name="Verona"]  a', expect_stream);
casper.thenClick('#global_filters [data-name="home"]    a', expect_home);
casper.thenClick('#global_filters [data-name="private"] a', expect_all_pm);
un_narrow();


common.then_log_out();

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});

var common = require('../common.js').common;

// Silence jslint errors about the global
/*global keep_pointer_in_view: true */
/*global process_visible_unread_messages: true */

function get_selector_num(selector_string) {
    var ret = casper.evaluate(function (selector_string) {
        return $(selector_string).text();
    }, {selector_string: selector_string});

    var num = parseInt(ret, 10);
    if (isNaN(num)) {
        num = 0;
    }
    return num;
}

// Othello
casper.start("http://localhost:9981/accounts/login");
common.then_log_in({username: 'othello@zulip.com', password: 'GX5MTQ+qYSzcmDoH'});

casper.then(function () {
    // Force a pointer update so we no longer have a -1 pointer in the db
    var a = casper.evaluate(function () {
        $.post("/json/update_pointer", {pointer: 1});
    });
});

common.then_log_out();

// Iago
common.then_log_in({username: 'iago@zulip.com', password: 'JhwLkBydEG1tAL5P'});

casper.then(function () {
    casper.test.info('Sending messages (this may take a while...)');
});

// Send interleaved messages to both stream Verona and Othello,
// so we can test both stream and PM unread counts.
var i;
for (i = 1; i <= 13; i++) {
    common.send_message('stream', {
        stream:  'Verona',
        subject: 'unread test',
        content: 'Iago unread stream message ' + i.toString()
    });
    common.send_message('private', {
        recipient: 'othello@zulip.com',
        content:   'Iago unread PM ' + i.toString()
    });
}
common.then_log_out();

// Othello
common.then_log_in({username: 'othello@zulip.com', password: 'GX5MTQ+qYSzcmDoH'});

var verona_sidebar_selector = "div[data-name='Verona'] .value";
var iago_sidebar_selector = "li[data-email='iago@zulip.com'] .value";

var last_stream_count;
var last_pm_count;

common.wait_for_load(function () {
    function send_key(key) { casper.page.sendEvent('keypress', key); casper.wait(50); }

    function scroll_to(ypos) {
        // Changing the scroll position in phantomjs doesn't seem to trigger on-scroll
        // handlers, so unread messages are not handled
        casper.page.scrollPosition = {top: ypos, left: 0};
        casper.evaluate(function () { keep_pointer_in_view();
                                      process_visible_unread_messages(); });
    }
    var i = 0;
    scroll_to(0);

    // Due to font size and height variance across platforms, we are restricted from checking specific
    // unread counts as they might not be consistent. However, we do know that after scrolling
    // down more messages should be marked as read
    var first_stream_count = get_selector_num(verona_sidebar_selector);
    var first_pm_count = get_selector_num(iago_sidebar_selector);
    for(i = 0; i < 1500; i += 100) {
        scroll_to(i);
    }

    last_stream_count = get_selector_num(verona_sidebar_selector);
    last_pm_count = get_selector_num(iago_sidebar_selector);
    casper.test.assert(last_stream_count < first_stream_count,
        "Unread count in stream sidebar decreases after scrolling");
    casper.test.assert(last_pm_count < first_pm_count,
        "Unread count in user sidebar decreases after scrolling");

});

// We need to be idle for a second to send a pointer update,
// then wait a little bit more to let the pointer update finish.
// Two seconds seems safe.
casper.wait(2000);

common.then_log_out();
common.then_log_in({username: 'othello@zulip.com', password: 'GX5MTQ+qYSzcmDoH'});
common.wait_for_load(function () {
    // Make sure logging out and in didn't change the unread count.
    casper.test.assertEquals(get_selector_num(verona_sidebar_selector),
                             last_stream_count,
                             'Stream sidebar unread correct on login');
    casper.test.assertEquals(get_selector_num(iago_sidebar_selector),
                             last_pm_count,
                             'User sidebar unread correct on login');
});

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});

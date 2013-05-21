var common = require('../common.js').common;

// NOTE this test will fail if run standalone, because
// other tests send a message before this one is run,
// changing the unread counts. uncomment line 43 to run
// standalone
// Silence jslint errors about the "process_visible_unread_messages" global
/*global process_visible_unread_messages: true */
/*global keep_pointer_in_view: true */

function send_with_content(content) {
    common.send_message('stream', {
            stream:  'Venice',
            subject: 'unread test',
            content: content
    });
}

// Iago
common.start_and_log_in(undefined, {width: 1280, height: 600});
casper.then(function () {
    send_with_content('Iago unread test 0');
});
common.then_log_out();

// Othello
casper.open("http://localhost:9981/accounts/login");
common.then_log_in({username: 'othello@humbughq.com', password: '52VeZqtHDCdAr5yM'});

casper.then(function () {
    // Force a pointer update so we no longer have a -1 pointer in the db
    var a = casper.evaluate(function () {
        $.post("/json/update_pointer", {pointer: 1});
    });
});

common.then_log_out();
common.then_log_in({username: 'iago@humbughq.com', password: 'FlokrWdZefyEWkfI'});

send_with_content('Iago unread test 1');
send_with_content('Iago unread test 2');
send_with_content('Iago unread test 3');
send_with_content('Iago unread test 4');
send_with_content('Iago unread test 5');
send_with_content('Iago unread test 6');
send_with_content('Iago unread test 7');
send_with_content('Iago unread test 8');
send_with_content('Iago unread test 9');
send_with_content('Iago unread test 10');
send_with_content('Iago unread test 11');
send_with_content('Iago unread test 12');
send_with_content('Iago unread test 13');
common.then_log_out();

common.then_log_in({username: 'othello@humbughq.com', password: '52VeZqtHDCdAr5yM'});
casper.then(function () {
    // Make sure we have 3 unread messages
    casper.test.assertSelectorHasText("a[href='#narrow/stream/Venice']", 'Venice', 'Unread count in sidebar is correct');
});

// Sending a message should not increase the count
send_with_content('Othello unread test 4');
send_with_content('Othello unread test 5');

casper.then(function () {
    function get_sidebar() { return casper.evaluate(function () { return $("a[href='#narrow/stream/Venice']").text(); }); }
    function get_sidebar_num() {
        var match = get_sidebar().match(/\w+\((\d+)\)/);
        if (match) {
           return parseInt(match[1], 10);
        } else {
           return 0;
        }
    }

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
    var sidebar_initial = get_sidebar_num();
    for(i = 0; i < 1500; i += 100) {
        scroll_to(i);
    }

    var sidebar_end = get_sidebar_num();
    casper.test.assert(sidebar_end < sidebar_initial, "Unread count in sidebar decreases after scrolling");

});
common.then_log_out();
common.then_log_in({username: 'othello@humbughq.com', password: '52VeZqtHDCdAr5yM'});
casper.then(function () {
    casper.test.assertSelectorHasText("a[href='#narrow/stream/Venice']", 'Venice', 'Sidebar unread correct on login');
});

// Run the above queued actions.
casper.run(function () {
    casper.test.done(3);
});

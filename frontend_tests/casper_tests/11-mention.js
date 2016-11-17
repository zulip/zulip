var common = require('../casper_lib/common.js').common;

common.start_and_log_in();
casper.verbonse = true;

casper.waitForSelector('#new_message_content', function () {
    casper.test.info('compose box visible');
    casper.page.sendEvent('keypress', "c"); // brings up the compose box
});

casper.then(function () {
    casper.fill('form[action^="/json/messages"]', {
        stream:  'Verona',
        subject: 'Test mention all'
    });
});
common.select_item_via_typeahead('#new_message_content', '@all', 'all');

casper.waitForText("Are you sure you want to mention all", function () {
    casper.test.info('Warning message appears when mentioning @all');
    casper.test.assertSelectorHasText('.compose-all-everyone', 'Are you sure you want to mention all');
});

casper.then( function () {
    common.turn_off_press_enter_to_send();
    casper.test.info('Click Send Button');
    casper.click('#compose-send-button');
});
casper.waitForText("Please remove @all", function () {
    casper.test.info('Error message appears when attempting to send a message without acknowledging the @all mention warning');
    casper.test.assertSelectorHasText('#error-msg', "Please remove @all / @everyone or acknowledge that you will be spamming everyone!");
});

casper.waitForSelector('.compose-all-everyone-confirm', function () {
    casper.click('.compose-all-everyone-confirm');
}, function () {
    casper.test.error('Could not click confirm button.');
});

casper.waitWhileVisible('.compose-all-everyone-confirm', function () {
    casper.test.info('Check that error messages are gone.');
    casper.test.assertNotVisible('.compose-all-everyone-msg');
    casper.test.assertNotVisible('#send-status');
});

casper.then( function () {
    casper.test.info('Click Send Button');
    casper.click('#compose-send-button');
});

casper.then( function () {
    common.expected_messages('zhome', ['Verona > Test mention all'],
     ["<p><span class=\"user-mention user-mention-me\" data-user-email=\"*\">@all</span> </p>"]
    );
});


common.then_log_out();

casper.run(function () {
    casper.test.done();
});

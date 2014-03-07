var common = require('../common.js').common;

common.start_and_log_in();

function then_edit_last_message() {
    casper.then(function () {
        casper.evaluate(function () {
            var msg = $('#zhome .message_row:last');
            msg.find('.info').click();
            $('.popover_edit_message').click();
        });
    });
    casper.waitForSelector(".message_edit_content");
}


// Send and edit a stream message

common.then_send_message('stream', {
    stream:  'Verona',
    subject: 'edits',
    content: 'test editing'
});

casper.waitForText("test editing");

then_edit_last_message();

casper.then(function () {
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.message_edit_topic').val("edited");
        msg.find('.message_edit_content').val("test edited");
        msg.find('.message_edit_save').click();
    });
});

casper.waitForSelector(".message_edit_notice", function () {
    casper.test.assertSelectorHasText(".last_message .message_content", "test edited");
});

common.then_send_message('private', {
    recipient: "cordelia@zulip.com",
    content: "test editing pm"
});

casper.waitForText("test editing pm");
then_edit_last_message();

casper.then(function () {
    casper.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.message_edit_content').val("test edited pm");
        msg.find('.message_edit_save').click();
    });
});

casper.waitForSelector(".private-message .message_edit_notice", function () {
    casper.test.assertSelectorHasText(".last_message .message_content", "test edited pm");
});

casper.run(function () {
    casper.test.done();
});

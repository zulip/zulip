var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

var last_message_id;
var msgs_qty;


casper.then(function () {
    casper.waitUntilVisible("#zhome");
});

casper.then(function () {
    msgs_qty = this.evaluate(function () {
        return $('#zhome .message_row').length;
    });
    last_message_id = this.evaluate(function () {
        var msg = $('#zhome .message_row:last');
        msg.find('.info').click();
        $('.delete_message').click();
        return msg.attr('id');
    });
});

casper.then(function () {
    casper.waitUntilVisible("#delete_message_modal", function () {
        casper.click('#do_delete_message_button');
    });
});

casper.then(function () {
    casper.waitFor(function check_length() {
        return casper.evaluate(function (expected_length) {
            return $('#zhome .message_row').length === expected_length;
        }, msgs_qty - 1);
    });
});

casper.then(function () {
    casper.test.assertDoesntExist(last_message_id);
});

casper.run(function () {
    casper.test.done();
});

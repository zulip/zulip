var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.waitUntilVisible("#streams_inline_cog", function () {
        casper.click("#streams_inline_cog");
    });
});

casper.then(function () {
    casper.waitUntilVisible(".right", function () {
        casper.click(".create_stream_button.button.small.rounded");
    });
});

casper.then(function () {
    casper.fill("form#stream_creation_form", {
        stream_name: "private_test_stream",
        privacy: "invite-only",
    }, true);
});

casper.then(function () {
    casper.waitWhileVisible("#stream_creating_indicator", function () {
        casper.waitForSelectorText("#stream_creation_form .stream_create_info", "Stream successfully created!");
        casper.test.info("Created a new private stream.");
    });
});

var stream_id;

casper.then(function () {
    casper.waitForSelector(".stream-row[data-stream-name='private_test_stream']", function () {
        stream_id = this.evaluate(function () {
            return $(".stream-row[data-stream-name='private_test_stream']").data("stream-id");
        });
        casper.click(".stream-row[data-stream-name='private_test_stream']");
    });
});

casper.then(function () {
    casper.waitForSelector(".subscription_settings[data-stream-id='" + stream_id + "']", function () {
        casper.test.assertSelectorHasText('.subscription_settings .stream-name', 'private_test_stream');
        casper.click(".subscription_settings .button.small.rounded.subscribe-button.sub_unsub_button ");
    });
});

casper.then(function () {
    casper.waitUntilVisible("#unsubscribe_stream_modal", function () {
        casper.test.info("Opened prompt for unsubscribing to a private stream for last user");
        casper.click("#do_unsubscribe_stream_button");
    });
});

casper.then(function () {
    casper.waitUntilVisible(".nothing-selected", function () {
        casper.test.assertDoesntExist(".stream-row[data-stream-name='private_test_stream']", "Unsubscribed from private stream");
    });
});

casper.run(function () {
    casper.test.done();
});

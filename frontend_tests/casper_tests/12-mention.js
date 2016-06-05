var common = require('../casper_lib/common.js').common;

common.start_and_log_in();
casper.verbonse = true;

casper.waitForSelector('#new_message_content', function () {
	casper.test.info('compose box visible????');
	casper.page.sendEvent('keypress', "c"); // brings up the compose box
//	casper.fill('form[action^="/json/messages"]', {
//		stream:  'Verona',
//		subject: '@all',
//		content: '@all test spamming everyone'
//	});
//	casper.click('#compose-send-button');
//	casper.waitForText("Are you sure you want to message all", function () {
//	});
});


function do_compose(str, item) {
    casper.then(function () {
		casper.test.info('Filling contents of compose box????');
		casper.fill('form[action^="/json/messages"]', {
			stream:  'Verona',
			subject: 'Test mention all',
		});
		casper.then(function () {
				casper.test.info('Start using typeahead');
			}
		);
        casper.evaluate(function (str, item) {
            // Set the value and then send a bogus keyup event to trigger
            // the typeahead.
            $('#new_message_content')
                .focus()
                .val(str)
                .trigger($.Event('keyup', { which: 0 }));

            // Trigger the typeahead.
            // Reaching into the guts of Bootstrap Typeahead like this is not
            // great, but I found it very hard to do it any other way.
            var tah = $('#new_message_content').data().typeahead;
            tah.mouseenter({
                currentTarget: $('.typeahead:visible li:contains("'+item+'")')[0]
            });
            tah.select();
        }, {str: str, item: item});
    });

	casper.waitForText("Are you sure you want to message all", function () {
		casper.test.assertVisible('#stream', 'Stream input box visible');
	});
}

var all_item = {
	special_item_text: "all (Notify everyone)",
	email: "all",
	// Always sort above, under the assumption that names will
	// be longer and only contain "all" as a substring.
	pm_recipient_count: Infinity,
	full_name: "all"
};

do_compose('@all', 'all');

// casper.waitUntilVisible('#stream', function () {
    // S: enter a new message with @all
    // A: warning message appears
    // S: enter more text in the message content
    // S: click YES
    // A: warning message disappears
    //
    // S: add @everyone to message
    // A: warning message
    // S: click send
    // A: error message
    // S: click YES
    // A: messages disappear
    // S: click send
    // A: message posted
//});

common.then_log_out();

casper.run(function () {
    casper.test.done();
});

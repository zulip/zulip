var common = require('../casper_lib/common.js').common;

common.start_and_log_in();

casper.then(function () {
    casper.test.info('Sending messages');
});

// setup environment: several messages to different topics
common.then_send_many([
    { stream:  'Verona', subject: 'copy-paste-subject #1',
      content: 'copy paste test A' },

    { stream:  'Verona', subject: 'copy-paste-subject #1',
      content: 'copy paste test B' },

    { stream:  'Verona', subject: 'copy-paste-subject #2',
      content: 'copy paste test C' },

    { stream:  'Verona', subject: 'copy-paste-subject #2',
      content: 'copy paste test D' },

    { stream:  'Verona', subject: 'copy-paste-subject #2',
      content: 'copy paste test E' },

    { stream:  'Verona', subject: 'copy-paste-subject #3',
      content: 'copy paste test F' },

    { stream:  'Verona', subject: 'copy-paste-subject #3',
      content: 'copy paste test G' },
]);

common.wait_for_receive(function () {
    common.expected_messages('zhome', [
        'Verona > copy-paste-subject #1',
        'Verona > copy-paste-subject #2',
        'Verona > copy-paste-subject #3',
    ], [
        '<p>copy paste test A</p>',
        '<p>copy paste test B</p>',
        '<p>copy paste test C</p>',
        '<p>copy paste test D</p>',
        '<p>copy paste test E</p>',
        '<p>copy paste test F</p>',
        '<p>copy paste test G</p>',
    ]);
});

casper.then(function () {
    casper.test.info('Messages were sent successfully');
});

function get_message_node(message) {
    return $('.message_row .message_content:contains("' + message + '")').get(0);
}

function copy_messages(start_message, end_message) {
    return casper.evaluate(function (get_message_node, start_message, end_message) {
        // select messages from start_message to end_message
        var selectedRange = document.createRange();
        selectedRange.setStart(get_message_node(start_message));
        selectedRange.setEnd(get_message_node(end_message));
        window.getSelection().removeAllRanges();
        window.getSelection().addRange(selectedRange);

        // emulate copy event
        var event = document.createEvent('Event');
        event.initEvent('copy', true, true);
        document.dispatchEvent(event);

        // find temp div with copied text
        var temp_div = $('#copytempdiv');
        return temp_div.children('p').get().map(function (p) { return p.textContent; });
    }, {
        get_message_node: get_message_node,
        start_message: start_message,
        end_message: end_message,
    });
}

// test copying first message from topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test C', 'copy paste test C');
    var expected_copied_lines = [];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by browser');
});

// test copying last message from topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test E', 'copy paste test E');
    var expected_copied_lines = [];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by browser');
});

// test copying two first messages from topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test C', 'copy paste test D');
    var expected_copied_lines = ['Iago: copy paste test C', 'Iago: copy paste test D'];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by custom handler');
});

// test copying all messages from topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test C', 'copy paste test E');
    var expected_copied_lines = ['Iago: copy paste test C', 'Iago: copy paste test D', 'Iago: copy paste test E'];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by custom handler');
});

// test copying last message from previous topic and first message from next topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test B', 'copy paste test C');
    var expected_copied_lines = [
        'Verona > copy-paste-subject #1 Today',
        'Iago: copy paste test B',
        'Verona > copy-paste-subject #2 Today',
        'Iago: copy paste test C',
    ];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by custom handler');
});

// test copying last message from previous topic and all messages from next topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test B', 'copy paste test E');
    var expected_copied_lines = [
        'Verona > copy-paste-subject #1 Today',
        'Iago: copy paste test B',
        'Verona > copy-paste-subject #2 Today',
        'Iago: copy paste test C',
        'Iago: copy paste test D',
        'Iago: copy paste test E',
    ];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by custom handler');
});

// test copying all messages from previous topic and first message from next topic
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test A', 'copy paste test C');
    var expected_copied_lines = [
        'Verona > copy-paste-subject #1 Today',
        'Iago: copy paste test A',
        'Iago: copy paste test B',
        'Verona > copy-paste-subject #2 Today',
        'Iago: copy paste test C',
    ];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by custom handler');
});

// test copying message from several topics
casper.then(function () {
    var actual_copied_lines = copy_messages('copy paste test B', 'copy paste test F');
    var expected_copied_lines = [
        'Verona > copy-paste-subject #1 Today',
        'Iago: copy paste test B',
        'Verona > copy-paste-subject #2 Today',
        'Iago: copy paste test C',
        'Iago: copy paste test D',
        'Iago: copy paste test E',
        'Verona > copy-paste-subject #3 Today',
        'Iago: copy paste test F',
    ];
    casper.test.assertEquals(actual_copied_lines, expected_copied_lines, 'Copying was handled by custom handler');
});

// Run the above queued actions.
casper.run(function () {
    casper.test.done();
});

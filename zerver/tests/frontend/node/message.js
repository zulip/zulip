var assert = require('assert');

add_dependencies({
    Handlebars: 'handlebars',
    templates: 'js/templates'
});

global.use_template('message');
global.$ = require('jquery');

(function test_message_handlebars() {
    var messages = [
        {
            include_recipient: true,
            display_recipient: 'devel',
            subject: 'testing',
            is_stream: true,
            content: 'This is message one.',
            last_edit_timestr: '11:00',
            starred: true
        },
        {
            content: 'This is message two.'
        }
    ];
    var args = {
        messages: messages
    };
    var html = global.templates.render('message', args);
    html = '<table class="message_table focused_table" id="zfilt">' + html + '</table>';

    global.write_test_output("test_message_handlebars", html);

    var first_message = $(html).find("td.messagebox:first");

    var first_message_text = first_message.find(".message_content").text().trim();
    assert.equal(first_message_text, "This is message one.");

    var starred_title = first_message.find(".star span").attr("title");
    assert.equal(starred_title, "Unstar this message");
}());

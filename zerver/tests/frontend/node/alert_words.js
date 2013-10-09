var assert = require('assert');

add_dependencies({
    _: 'third/underscore/underscore.js'
});

set_global('page_params', {
    alert_words: ['alertone', 'alerttwo', 'alertthree', 'al*rt.*s', '.+'],
    email: 'tester@zulip.com'
});

set_global('feature_flags', {
    alert_words: true
});

var alert_words = require('js/alert_words.js');

var regular_message = { sender_email: 'another@zulip.com', content: '<p>a message</p>',
                        flags: [] };
var own_message = { sender_email: 'tester@zulip.com', content: '<p>hey this message alertone</p>',
                        flags: ['has_alert_word'] };
var other_message = { sender_email: 'another@zulip.com', content: '<p>another alertone message</p>',
                        flags: ['has_alert_word'] };
var caps_message = { sender_email: 'another@zulip.com', content: '<p>another ALERTtwo message</p>',
                        flags: ['has_alert_word'] };
var alertwordboundary_message = { sender_email: 'another@zulip.com',
                                  content: '<p>another alertthreemessage</p>', flags: [] };
var multialert_message = { sender_email: 'another@zulip.com', content:
                           '<p>another alertthreemessage alertone and then alerttwo</p>',
                           flags: ['has_alert_word'] };
var unsafe_word_message = { sender_email: 'another@zulip.com', content: '<p>gotta al*rt.*s all</p>',
                            flags: ['has_alert_word'] };
var alert_in_url_message = { sender_email: 'another@zulip.com', content: '<p>http://www.google.com/alertone/me</p>',
                            flags: ['has_alert_word'] };
var question_word_message = { sender_email: 'another@zulip.com', content: '<p>still alertone? me</p>',
                            flags: ['has_alert_word'] };

(function test_notifications() {
    assert.equal(alert_words.notifies(regular_message), false);
    assert.equal(alert_words.notifies(own_message), false);
    assert.equal(alert_words.notifies(other_message), true);
    assert.equal(alert_words.notifies(caps_message), true);
    assert.equal(alert_words.notifies(alertwordboundary_message), false);
    assert.equal(alert_words.notifies(multialert_message), true);
    assert.equal(alert_words.notifies(unsafe_word_message), true);
}());

(function test_munging() {
    var saved_content = regular_message.content;
    alert_words.process_message(regular_message);
    assert.equal(saved_content, regular_message.content);

    saved_content = alertwordboundary_message.content;
    alert_words.process_message(alertwordboundary_message);
    assert.equal(alertwordboundary_message.content, saved_content);

    alert_words.process_message(other_message);
    assert.equal(other_message.content, "<p>another <span class='alert-word'>alertone</span> message</p>");
    alert_words.process_message(caps_message);
    assert.equal(caps_message.content, "<p>another <span class='alert-word'>ALERTtwo</span> message</p>");

    alert_words.process_message(multialert_message);
    assert.equal(multialert_message.content, "<p>another alertthreemessage <span class='alert-word'>alertone</span> and then <span class='alert-word'>alerttwo</span></p>");

    alert_words.process_message(unsafe_word_message);
    assert.equal(unsafe_word_message.content, "<p>gotta <span class='alert-word'>al*rt.*s</span> all</p>");

    alert_words.process_message(alert_in_url_message);
    assert.equal(alert_in_url_message.content, "<p>http://www.google.com/alertone/me</p>");

    alert_words.process_message(question_word_message);
    assert.equal(question_word_message.content, "<p>still <span class='alert-word'>alertone</span>? me</p>");
}());
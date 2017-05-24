add_dependencies({
   people: 'js/people.js',
});

set_global('page_params', {
    alert_words: ['alertone', 'alerttwo', 'alertthree', 'al*rt.*s', '.+'],
});

set_global('feature_flags', {
    alert_words: true,
});

global.people.add({
    email: 'tester@zulip.com',
    full_name: 'Tester von Tester',
    user_id: 42,
});

global.people.initialize_current_user(42);

var alert_words = require('js/alert_words.js');

var regular_message = { sender_email: 'another@zulip.com', content: '<p>a message</p>'};
var own_message = { sender_email: 'tester@zulip.com', content: '<p>hey this message alertone</p>',
                    alerted: true };
var other_message = { sender_email: 'another@zulip.com', content: '<p>another alertone message</p>',
                      alerted: true };
var caps_message = { sender_email: 'another@zulip.com', content: '<p>another ALERTtwo message</p>',
                     alerted: true };
var alertwordboundary_message = { sender_email: 'another@zulip.com',
                                  content: '<p>another alertthreemessage</p>', alerted: false };
var multialert_message = { sender_email: 'another@zulip.com', content:
                           '<p>another alertthreemessage alertone and then alerttwo</p>',
                           alerted: true };
var unsafe_word_message = { sender_email: 'another@zulip.com', content: '<p>gotta al*rt.*s all</p>',
                            alerted: true };
var alert_in_url_message = { sender_email: 'another@zulip.com', content: '<p>http://www.google.com/alertone/me</p>',
                            alerted: true };
var question_word_message = { sender_email: 'another@zulip.com', content: '<p>still alertone? me</p>',
                            alerted: true };

var alert_domain_message = { sender_email: 'another@zulip.com', content: '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.alerttwo.us/foo/bar</a></p>',
                     alerted: true };


(function test_notifications() {
    assert(!alert_words.notifies(regular_message));
    assert(!alert_words.notifies(own_message));
    assert(alert_words.notifies(other_message));
    assert(alert_words.notifies(caps_message));
    assert(!alert_words.notifies(alertwordboundary_message));
    assert(alert_words.notifies(multialert_message));
    assert(alert_words.notifies(unsafe_word_message));
    assert(alert_words.notifies(alert_domain_message));
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

    alert_words.process_message(alert_domain_message);
    assert.equal(alert_domain_message.content, '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.<span class=\'alert-word\'>alerttwo</span>.us/foo/bar</a></p>');
}());

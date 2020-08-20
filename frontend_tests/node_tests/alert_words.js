"use strict";

const params = {
    alert_words: ["alertone", "alerttwo", "alertthree", "al*rt.*s", ".+", "emoji"],
};

const people = zrequire("people");
zrequire("alert_words");

alert_words.initialize(params);

people.add_active_user({
    email: "tester@zulip.com",
    full_name: "Tester von Tester",
    user_id: 42,
});

people.initialize_current_user(42);

const regular_message = {
    sender_email: "another@zulip.com",
    content: "<p>a message</p>",
};
const own_message = {
    sender_email: "tester@zulip.com",
    content: "<p>hey this message alertone</p>",
    alerted: true,
};
const other_message = {
    sender_email: "another@zulip.com",
    content: "<p>another alertone message</p>",
    alerted: true,
};
const caps_message = {
    sender_email: "another@zulip.com",
    content: "<p>another ALERTtwo message</p>",
    alerted: true,
};
const alertwordboundary_message = {
    sender_email: "another@zulip.com",
    content: "<p>another alertthreemessage</p>",
    alerted: false,
};
const multialert_message = {
    sender_email: "another@zulip.com",
    content: "<p>another alertthreemessage alertone and then alerttwo</p>",
    alerted: true,
};
const unsafe_word_message = {
    sender_email: "another@zulip.com",
    content: "<p>gotta al*rt.*s all</p>",
    alerted: true,
};
const alert_in_url_message = {
    sender_email: "another@zulip.com",
    content: "<p>http://www.google.com/alertone/me</p>",
    alerted: true,
};
const question_word_message = {
    sender_email: "another@zulip.com",
    content: "<p>still alertone? me</p>",
    alerted: true,
};

const alert_domain_message = {
    sender_email: "another@zulip.com",
    content:
        '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.alerttwo.us/foo/bar</a></p>',
    alerted: true,
};
// This test ensure we are not mucking up rendered HTML content.
const message_with_emoji = {
    sender_email: "another@zulip.com",
    content:
        '<p>I <img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2764.png" title="heart"> emoji!</p>',
    alerted: true,
};

run_test("notifications", () => {
    assert(!alert_words.notifies(regular_message));
    assert(!alert_words.notifies(own_message));
    assert(alert_words.notifies(other_message));
    assert(alert_words.notifies(caps_message));
    assert(!alert_words.notifies(alertwordboundary_message));
    assert(alert_words.notifies(multialert_message));
    assert(alert_words.notifies(unsafe_word_message));
    assert(alert_words.notifies(alert_domain_message));
    assert(alert_words.notifies(message_with_emoji));
});

run_test("munging", () => {
    let saved_content = regular_message.content;
    alert_words.process_message(regular_message);
    assert.equal(saved_content, regular_message.content);

    saved_content = alertwordboundary_message.content;
    alert_words.process_message(alertwordboundary_message);
    assert.equal(alertwordboundary_message.content, saved_content);

    alert_words.process_message(other_message);
    assert.equal(
        other_message.content,
        "<p>another <span class='alert-word'>alertone</span> message</p>",
    );
    alert_words.process_message(caps_message);
    assert.equal(
        caps_message.content,
        "<p>another <span class='alert-word'>ALERTtwo</span> message</p>",
    );

    alert_words.process_message(multialert_message);
    assert.equal(
        multialert_message.content,
        "<p>another alertthreemessage <span class='alert-word'>alertone</span> and then <span class='alert-word'>alerttwo</span></p>",
    );

    alert_words.process_message(unsafe_word_message);
    assert.equal(
        unsafe_word_message.content,
        "<p>gotta <span class='alert-word'>al*rt.*s</span> all</p>",
    );

    alert_words.process_message(alert_in_url_message);
    assert.equal(alert_in_url_message.content, "<p>http://www.google.com/alertone/me</p>");

    alert_words.process_message(question_word_message);
    assert.equal(
        question_word_message.content,
        "<p>still <span class='alert-word'>alertone</span>? me</p>",
    );

    alert_words.process_message(alert_domain_message);
    assert.equal(
        alert_domain_message.content,
        '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.<span class=\'alert-word\'>alerttwo</span>.us/foo/bar</a></p>',
    );

    alert_words.process_message(message_with_emoji);
    assert.equal(
        message_with_emoji.content,
        '<p>I <img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2764.png" title="heart"> <span class=\'alert-word\'>emoji</span>!</p>',
    );
});

run_test("basic get/set operations", () => {
    assert(!alert_words.has_alert_word("breakfast"));
    assert(!alert_words.has_alert_word("lunch"));
    alert_words.set_words(["breakfast", "lunch"]);
    assert(alert_words.has_alert_word("breakfast"));
    assert(alert_words.has_alert_word("lunch"));
    assert(!alert_words.has_alert_word("dinner"));
});

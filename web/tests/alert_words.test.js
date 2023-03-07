"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

set_global("page_params", {
    is_spectator: false,
});

const params = {
    alert_words: [
        "alertone",
        "alerttwo",
        "alertthree",
        "al*rt.*s",
        ".+",
        "emoji",
        "FD&C",
        "<3",
        ">8",
        "5'11\"",
    ],
};

const people = zrequire("people");
const alert_words = zrequire("alert_words");

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
    content: "<p>another emoji alertone and then alerttwo</p>",
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

const typo_word_message = {
    sender_email: "another@zulip.com",
    content: "<p>alertones alerttwo alerttwo alertthreez</p>",
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
    assert.ok(!alert_words.notifies(regular_message));
    assert.ok(!alert_words.notifies(own_message));
    assert.ok(alert_words.notifies(other_message));
    assert.ok(alert_words.notifies(caps_message));
    assert.ok(!alert_words.notifies(alertwordboundary_message));
    assert.ok(alert_words.notifies(multialert_message));
    assert.ok(alert_words.notifies(unsafe_word_message));
    assert.ok(alert_words.notifies(alert_domain_message));
    assert.ok(alert_words.notifies(message_with_emoji));
});

run_test("munging", () => {
    alert_words.initialize(params);

    let saved_content = regular_message.content;
    alert_words.process_message(regular_message);
    assert.equal(saved_content, regular_message.content);

    saved_content = alertwordboundary_message.content;
    alert_words.process_message(alertwordboundary_message);
    assert.equal(alertwordboundary_message.content, saved_content);

    function assert_transform(message, expected_new_content) {
        const msg = {...message};
        alert_words.process_message(msg);
        assert.equal(msg.content, expected_new_content);
    }

    assert_transform(
        other_message,
        "<p>another <span class='alert-word'>alertone</span> message</p>",
    );

    assert_transform(
        caps_message,
        "<p>another <span class='alert-word'>ALERTtwo</span> message</p>",
    );

    assert_transform(
        multialert_message,
        "<p>another <span class='alert-word'>emoji</span> <span class='alert-word'>alertone</span> and then <span class='alert-word'>alerttwo</span></p>",
    );

    assert_transform(
        unsafe_word_message,
        "<p>gotta <span class='alert-word'>al*rt.*s</span> all</p>",
    );

    assert_transform(alert_in_url_message, "<p>http://www.google.com/alertone/me</p>");

    assert_transform(
        question_word_message,
        "<p>still <span class='alert-word'>alertone</span>? me</p>",
    );

    assert_transform(
        typo_word_message,
        "<p>alertones <span class='alert-word'>alerttwo</span> <span class='alert-word'>alerttwo</span> alertthreez</p>",
    );

    assert_transform(
        alert_domain_message,
        '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.<span class=\'alert-word\'>alerttwo</span>.us/foo/bar</a></p>',
    );

    assert_transform(
        message_with_emoji,
        '<p>I <img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2764.png" title="heart"> <span class=\'alert-word\'>emoji</span>!</p>',
    );

    assert_transform(
        {
            sender_email: "another@zulip.com",
            content: `<p>FD&amp;C &lt;3 &gt;8 5'11" 5&#39;11&quot;</p>`,
            alerted: true,
        },
        `<p><span class='alert-word'>FD&amp;C</span> <span class='alert-word'>&lt;3</span> <span class='alert-word'>&gt;8</span> <span class='alert-word'>5'11"</span> <span class='alert-word'>5&#39;11&quot;</span></p>`,
    );
});

run_test("basic get/set operations", () => {
    alert_words.initialize({alert_words: []});
    assert.ok(!alert_words.has_alert_word("breakfast"));
    assert.ok(!alert_words.has_alert_word("lunch"));
    alert_words.set_words(["breakfast", "lunch"]);
    assert.ok(alert_words.has_alert_word("breakfast"));
    assert.ok(alert_words.has_alert_word("lunch"));
    assert.ok(!alert_words.has_alert_word("dinner"));
});

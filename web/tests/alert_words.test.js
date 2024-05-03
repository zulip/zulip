"use strict";

const {strict: assert} = require("assert");

const {set_global, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

set_global("page_params", {
    is_spectator: false,
});

const params = {
    watched_phrases: [
        {watched_phrase: "alertone"},
        {watched_phrase: "alerttwo"},
        {watched_phrase: "alertthree"},
        {watched_phrase: "al*rt.*s"},
        {watched_phrase: ".+"},
        {watched_phrase: "emoji"},
        {watched_phrase: "FD&C"},
        {watched_phrase: "<3"},
        {watched_phrase: ">8"},
        {watched_phrase: "5'11\""},
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
    watched: true,
};
const other_message = {
    sender_email: "another@zulip.com",
    content: "<p>another alertone message</p>",
    watched: true,
};
const caps_message = {
    sender_email: "another@zulip.com",
    content: "<p>another ALERTtwo message</p>",
    watched: true,
};
const alertwordboundary_message = {
    sender_email: "another@zulip.com",
    content: "<p>another alertthreemessage</p>",
    watched: false,
};
const multialert_message = {
    sender_email: "another@zulip.com",
    content: "<p>another emoji alertone and then alerttwo</p>",
    watched: true,
};
const unsafe_word_message = {
    sender_email: "another@zulip.com",
    content: "<p>gotta al*rt.*s all</p>",
    watched: true,
};
const alert_in_url_message = {
    sender_email: "another@zulip.com",
    content: "<p>http://www.google.com/alertone/me</p>",
    watched: true,
};
const question_word_message = {
    sender_email: "another@zulip.com",
    content: "<p>still alertone? me</p>",
    watched: true,
};

const typo_word_message = {
    sender_email: "another@zulip.com",
    content: "<p>alertones alerttwo alerttwo alertthreez</p>",
    watched: true,
};

const alert_domain_message = {
    sender_email: "another@zulip.com",
    content:
        '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.alerttwo.us/foo/bar</a></p>',
    watched: true,
};
// This test ensure we are not mucking up rendered HTML content.
const message_with_emoji = {
    sender_email: "another@zulip.com",
    content:
        '<p>I <img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2764.png" title="heart"> emoji!</p>',
    watched: true,
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
    assert.deepEqual(alert_words.get_watched_phrase_data(), [
        {watched_phrase: "alertthree"},
        {watched_phrase: "alertone"},
        {watched_phrase: "alerttwo"},
        {watched_phrase: "al*rt.*s"},
        {watched_phrase: "emoji"},
        {watched_phrase: `5'11"`},
        {watched_phrase: "FD&C"},
        {watched_phrase: ".+"},
        {watched_phrase: "<3"},
        {watched_phrase: ">8"},
    ]);
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
        "<p>another <span class='watched-phrase'>alertone</span> message</p>",
    );

    assert_transform(
        caps_message,
        "<p>another <span class='watched-phrase'>ALERTtwo</span> message</p>",
    );

    assert_transform(
        multialert_message,
        "<p>another <span class='watched-phrase'>emoji</span> <span class='watched-phrase'>alertone</span> and then <span class='watched-phrase'>alerttwo</span></p>",
    );

    assert_transform(
        unsafe_word_message,
        "<p>gotta <span class='watched-phrase'>al*rt.*s</span> all</p>",
    );

    assert_transform(alert_in_url_message, "<p>http://www.google.com/alertone/me</p>");

    assert_transform(
        question_word_message,
        "<p>still <span class='watched-phrase'>alertone</span>? me</p>",
    );

    assert_transform(
        typo_word_message,
        "<p>alertones <span class='watched-phrase'>alerttwo</span> <span class='watched-phrase'>alerttwo</span> alertthreez</p>",
    );

    assert_transform(
        alert_domain_message,
        '<p>now with link <a href="http://www.alerttwo.us/foo/bar" target="_blank" title="http://www.alerttwo.us/foo/bar">www.<span class=\'watched-phrase\'>alerttwo</span>.us/foo/bar</a></p>',
    );

    assert_transform(
        message_with_emoji,
        '<p>I <img alt=":heart:" class="emoji" src="/static/generated/emoji/images/emoji/unicode/2764.png" title="heart"> <span class=\'watched-phrase\'>emoji</span>!</p>',
    );

    assert_transform(
        {
            sender_email: "another@zulip.com",
            content: `<p>FD&amp;C &lt;3 &gt;8 5'11" 5&#39;11&quot;</p>`,
            watched: true,
        },
        `<p><span class='watched-phrase'>FD&amp;C</span> <span class='watched-phrase'>&lt;3</span> <span class='watched-phrase'>&gt;8</span> <span class='watched-phrase'>5'11"</span> <span class='watched-phrase'>5&#39;11&quot;</span></p>`,
    );
});

run_test("basic get/set operations", () => {
    alert_words.initialize({watched_phrases: []});
    assert.ok(!alert_words.has_watched_phrase("breakfast"));
    assert.ok(!alert_words.has_watched_phrase("lunch"));
    alert_words.set_watched_phrases([{watched_phrase: "breakfast"}, {watched_phrase: "lunch"}]);
    assert.ok(alert_words.has_watched_phrase("breakfast"));
    assert.ok(alert_words.has_watched_phrase("lunch"));
    assert.ok(!alert_words.has_watched_phrase("dinner"));
});

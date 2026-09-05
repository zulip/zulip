"use strict";

const assert = require("node:assert/strict");

const {make_stream} = require("./lib/example_stream.cjs");
const {make_user} = require("./lib/example_user.cjs");
const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const {$} = require("./lib/zjquery.cjs");

mock_esm("../src/electron_bridge");
mock_esm("../src/spoilers", {hide_spoilers_in_notification() {}});
const channel = mock_esm("../src/channel");
const settings_data = mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
});
const unread_ops = mock_esm("../src/unread_ops", {
    // The default for these tests is a user who is not watching the message
    // feed, and so has not already seen the reaction arrive.
    viewport_is_visible_and_focused: () => false,
});
const message_lists = mock_esm("../src/message_lists", {current: undefined});

const desktop_notifications = zrequire("desktop_notifications");
const message_helper = zrequire("message_helper");
const message_store = zrequire("message_store");
const muted_users = zrequire("muted_users");
const people = zrequire("people");
const reaction_notifications = zrequire("reaction_notifications");
const stream_data = zrequire("stream_data");
const user_topics = zrequire("user_topics");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

set_realm({});
const current_user = {user_id: 1};
set_current_user(current_user);
people.initialize_current_user(current_user.user_id);
const user_settings = {};
initialize_user_settings({user_settings});

const me = make_user({user_id: current_user.user_id, full_name: "Me Myself"});
const alice = make_user({user_id: 2, full_name: "Alice"});
const bob = make_user({user_id: 3, full_name: "Bob"});
const cindy = make_user({user_id: 4, full_name: "Cindy"});
const muted_reactor = make_user({user_id: 5, full_name: "Muted"});
for (const user of [me, alice, bob, cindy, muted_reactor]) {
    people.add_active_user(user);
}

// A user this client has no record of, as happens in a realm where users
// cannot access all other users.
const inaccessible_user_id = 99;

const general = make_stream({name: "general", stream_id: 10, is_muted: false});
const muted = make_stream({name: "muted", stream_id: 20, is_muted: true});
stream_data.add_sub_for_tests(general);
stream_data.add_sub_for_tests(muted);

for (const [stream, topic, visibility_policy] of [
    [general, "muted topic", user_topics.all_visibility_policies.MUTED],
    [muted, "unmuted topic", user_topics.all_visibility_policies.UNMUTED],
    [muted, "followed topic", user_topics.all_visibility_policies.FOLLOWED],
]) {
    user_topics.update_user_topics(stream.stream_id, stream.name, topic, visibility_policy);
}

function test(label, f) {
    run_test(label, (helpers) => {
        // The cached messages and live notifications a test makes are its
        // own; the next test starts with neither.
        message_store.clear_for_testing();
        desktop_notifications.notice_memory.clear();
        muted_users.set_muted_users([]);
        helpers.override(user_settings, "enable_reaction_desktop_notifications", true);
        helpers.override(user_settings, "enable_reaction_audible_notifications", false);
        helpers.override(user_settings, "notification_sound", "ding");
        helpers.override(user_settings, "emojiset", "google");
        f(helpers);
    });
}

const tada = {reaction_type: "unicode_emoji", emoji_name: "tada", emoji_code: "1f389"};
const thumbs_up = {reaction_type: "unicode_emoji", emoji_name: "thumbs_up", emoji_code: "1f44d"};
const realm_tada = {reaction_type: "realm_emoji", emoji_name: "tada", emoji_code: "5"};
// A realm emoji that took over the name of the one above, as happens when a
// custom emoji is deactivated and a new one is uploaded with the same name.
const newer_realm_tada = {reaction_type: "realm_emoji", emoji_name: "tada", emoji_code: "9"};
// A deactivated custom emoji, whose name is absent from `emoji.emojis_by_name`
// but which can still receive new votes.
const deactivated_realm_emoji = {
    reaction_type: "realm_emoji",
    emoji_name: "deactivated_custom",
    emoji_code: "1234",
};
const invalid_unicode_emoji = {
    reaction_type: "unicode_emoji",
    emoji_name: "bogus",
    emoji_code: "not-a-codepoint",
};

function reaction_event(message_id, user_id, emoji = tada) {
    // Every reaction here is to one of the current user's own messages, which
    // is what makes it a candidate for a notification at all.
    return {message_id, message_sender_id: current_user.user_id, user_id, ...emoji};
}

function added(event) {
    return {...event, op: "add"};
}

function retracted(event) {
    return {...event, op: "remove"};
}

function received_reaction(event) {
    reaction_notifications.received_reactions([added(event)]);
}

function removed_reaction(event) {
    reaction_notifications.received_reactions([retracted(event)]);
}

function stub_notification_api(permission = "granted") {
    const notices = {
        last_title: undefined,
        last_body: undefined,
        last_icon: undefined,
        last_tag: undefined,
        title_by_tag: new Map(),
        closed_tags: [],
        // Counts how many notifications have been shown, so tests can verify
        // that an operation does (or does not) pop one up.
        shown_count: 0,
        close_handlers: new Map(),
    };

    class StubNotification {
        static permission = permission;

        constructor(title, {icon, body, tag}) {
            this.tag = tag;
            notices.last_title = title;
            notices.last_body = body;
            notices.last_icon = icon;
            notices.last_tag = tag;
            notices.title_by_tag.set(tag, title);
            notices.shown_count += 1;
        }

        addEventListener(type, handler) {
            if (type === "close") {
                notices.close_handlers.set(this, handler);
            }
        }

        close() {
            notices.closed_tags.push(this.tag);
            // Dispatch the close event before returning, as an implementation
            // whose close() is not asynchronous does.
            notices.close_handlers.get(this)();
        }
    }

    desktop_notifications.set_notification_api(StubNotification);
    return notices;
}

function stub_message_content_parsing() {
    // The notification body is built by parsing message HTML through jQuery,
    // which the node test environment stubs.
    const $emoji_stub = $.create("emoji-stub");
    $emoji_stub.set_matches("img", false);
    $emoji_stub.set_contents([]);
    const $katex_stub = $.set_results("katex-stub", []);
    $("<div>").set_find_results(".emoji", $emoji_stub);
    $("<div>").set_find_results("span.katex", $katex_stub);
    $("<div>").set_children([]);
}

function my_channel_message(id) {
    return {
        id,
        type: "stream",
        content: "<p>my channel message</p>",
        stream_id: general.stream_id,
        topic: "whatever",
    };
}

function raw_message(id) {
    return {
        avatar_url: "https://example.com/avatar.png",
        client: "website",
        content: "<p>a message</p>",
        content_type: "text/html",
        display_recipient: general.name,
        id,
        is_me_message: false,
        reactions: [],
        sender_email: me.email,
        sender_full_name: me.full_name,
        sender_id: current_user.user_id,
        submessages: [],
        timestamp: 1000,
        flags: [],
        type: "stream",
        stream_id: general.stream_id,
        topic: "whatever",
        topic_links: [],
    };
}

function cache_message(id) {
    message_helper.process_new_server_message(raw_message(id));
}

function react(message, user_id, emoji = tada, desktop_notify = true) {
    reaction_notifications.process_notification({
        message,
        reaction_event: reaction_event(message.id, user_id, emoji),
        desktop_notify,
    });
}

test("reaction_is_notifiable honors muted channels and topics", () => {
    const cases = [
        // A reaction to a message in a muted channel does not notify, unless
        // the topic overrides the channel's visibility.
        {stream: muted, topic: "a topic that inherits visibility", notifiable: false},
        {stream: muted, topic: "unmuted topic", notifiable: true},
        {stream: muted, topic: "followed topic", notifiable: true},
        // Nor does one to a muted topic in a channel that is not muted.
        {stream: general, topic: "muted topic", notifiable: false},
        {stream: general, topic: "whatever", notifiable: true},
    ];

    for (const [i, {stream, topic, notifiable}] of cases.entries()) {
        const message = {id: i, type: "stream", stream_id: stream.stream_id, topic};
        assert.equal(
            reaction_notifications.reaction_is_notifiable(message),
            notifiable,
            `${stream.name} > ${topic}`,
        );
    }

    // A direct message has no channel or topic to mute.
    assert.ok(reaction_notifications.reaction_is_notifiable({id: 100, type: "private"}));
});

test("reactions that cannot notify are dropped without a fetch", ({override}) => {
    // Reaction events are delivered to everyone who can see the message.
    // received_reactions must therefore run the message-independent checks
    // before fetching an uncached message from the server, so we don't make a
    // request for essentially every reaction in a busy channel.
    stub_notification_api();
    let get_called = false;
    override(channel, "get", () => {
        get_called = true;
    });
    override(user_settings, "enable_reaction_audible_notifications", true);

    // Not in the message cache, so the notifiable case below fetches it.
    const event = reaction_event(987654, alice.user_id);

    // Baseline: an unfocused user with reaction notifications enabled fetches
    // their own uncached message so it can build a notification.
    received_reaction(event);
    assert.ok(get_called);

    // A reaction by the current user is dropped without a fetch.
    get_called = false;
    received_reaction({...event, user_id: current_user.user_id});
    assert.ok(!get_called);

    // A reaction to someone else's message can never notify, and the event
    // says whose message it is, so it is dropped without a fetch. This is what
    // keeps reactions in a busy organization from costing a request each.
    get_called = false;
    received_reaction({...event, message_sender_id: alice.user_id});
    assert.ok(!get_called);

    // A reaction from a muted user can never notify either, and whether the
    // reactor is muted does not depend on the message, so it too is dropped
    // without a fetch.
    muted_users.add_muted_user(muted_reactor.user_id);
    get_called = false;
    received_reaction({...event, user_id: muted_reactor.user_id});
    assert.ok(!get_called);

    // Note that whether the user is watching the message feed is not one of
    // the checks made here: it needs the message, so it is made per message
    // once we have one. See the test below.

    // With both reaction notification settings disabled, nothing is fetched.
    override(user_settings, "enable_reaction_desktop_notifications", false);
    override(user_settings, "enable_reaction_audible_notifications", false);
    get_called = false;
    received_reaction(event);
    assert.ok(!get_called);

    // With only the desktop setting on, a fetch happens only once the browser
    // notification permission has actually been granted; otherwise no
    // notification could ever result, so we skip the request. Permission is
    // read from NotificationAPI.permission.
    override(user_settings, "enable_reaction_desktop_notifications", true);
    stub_notification_api("denied");
    get_called = false;
    received_reaction(event);
    assert.ok(!get_called);

    stub_notification_api();
    get_called = false;
    received_reaction(event);
    assert.ok(get_called);
});

test("reaction notification titles", () => {
    const notices = stub_notification_api();
    stub_message_content_parsing();

    // The title credits the newest reactor first, and counts the rest.
    const message = my_channel_message(3300);
    react(message, alice.user_id);
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");
    react(message, bob.user_id);
    assert.equal(notices.last_title, "translated: Bob and Alice reacted with 🎉");
    react(message, cindy.user_id);
    assert.equal(notices.last_title, "translated: Cindy and 2 others reacted with 🎉");

    // Unicode emoji are rendered as the glyph itself; realm emoji as
    // `:emoji_name:`. The realm emoji named "tada" is a different reaction
    // from the Unicode :tada: -- a realm emoji may be named after a Unicode
    // emoji -- and renders differently, so both are listed.
    const other_message = my_channel_message(3310);
    react(other_message, alice.user_id);
    react(other_message, bob.user_id, realm_tada);
    assert.equal(notices.last_title, "translated: Bob and Alice reacted with :tada:, 🎉");

    // A newer realm emoji that reused the name renders the same way, so it
    // does not add a second `:tada:` to the title.
    react(other_message, alice.user_id, newer_realm_tada);
    assert.equal(notices.last_title, "translated: Alice and Bob reacted with :tada:, 🎉");

    // A reaction with a realm emoji that is no longer active is still
    // rendered from the event's own fields.
    react(other_message, bob.user_id, deactivated_realm_emoji);
    assert.ok(notices.last_title.includes(":deactivated_custom:"));

    // A unicode reaction whose emoji_code is not a valid codepoint cannot be
    // rendered as a glyph. That should never reach a client, so it is logged,
    // and the title falls back to `:emoji_name:` rather than showing the user
    // a placeholder that names no emoji at all.
    blueslip.expect("error", "Invalid unicode codepoint for emoji");
    react(other_message, bob.user_id, invalid_unicode_emoji);
    assert.ok(notices.last_title.includes(":bogus:"));
    assert.ok(!notices.last_title.includes("invalid_emoji"));
});

test("reactions to one message share a notification", () => {
    const notices = stub_notification_api();
    stub_message_content_parsing();
    const message = my_channel_message(3300);
    const other_message = my_channel_message(3400);

    react(message, alice.user_id);
    const notifications = desktop_notifications.get_notifications();
    assert.equal(notifications.size, 1);
    assert.ok(notifications.has(message.id.toString()));
    assert.equal(notices.last_tag, message.id.toString());

    // Further reactions to the same message update that one notification,
    // rather than stacking up.
    const superseded_notification = notifications.get(message.id.toString()).obj;
    react(message, bob.user_id);
    react(message, bob.user_id, thumbs_up);
    assert.equal(desktop_notifications.get_notifications().size, 1);

    // A reaction to another message gets a notification of its own.
    react(other_message, alice.user_id);
    assert.equal(desktop_notifications.get_notifications().size, 2);

    // The reactions credited in a notification are stored in its notice_memory
    // entry, so they must survive that entry being replaced when a further
    // reaction supersedes the notification, and must not be discarded by the
    // superseded notification's own close event arriving late.
    notices.close_handlers.get(superseded_notification)();
    assert.equal(desktop_notifications.get_notifications().size, 2);
    react(message, cindy.user_id);
    assert.equal(notices.last_title, "translated: Cindy and 2 others reacted with 🎉, 👍");

    // Closing a reaction notification -- as the message-read and window-focus
    // handlers do -- discards the reactions stored with it, so a later
    // reaction starts a fresh notification crediting only its own reactor
    // rather than resurrecting the earlier ones.
    desktop_notifications.close_notification(message.id);
    assert.equal(desktop_notifications.get_notifications().size, 1);
    react(message, bob.user_id);
    assert.equal(notices.last_title, "translated: Bob reacted with 🎉");
});

test("removing a reaction updates or dismisses its notification", () => {
    const notices = stub_notification_api();
    stub_message_content_parsing();
    const message = my_channel_message(3300);
    react(message, alice.user_id);
    react(message, bob.user_id);
    react(message, bob.user_id, thumbs_up);

    // Removing one reaction keeps the notification -- reactions from other
    // users and other emoji survive -- but must not pop up a new
    // notification, since a removed reaction is not new activity.
    notices.shown_count = 0;
    removed_reaction(reaction_event(message.id, bob.user_id, thumbs_up));
    assert.ok(desktop_notifications.get_notifications().has(message.id.toString()));
    assert.equal(notices.shown_count, 0);

    // Removing a reaction that was never notified about leaves the
    // notification untouched.
    removed_reaction(reaction_event(message.id, cindy.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 1);

    // Removing a reaction for a message with no notification is a no-op.
    removed_reaction(reaction_event(424_242, alice.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 1);

    // The notification is dismissed only once no notified reaction remains.
    notices.closed_tags.length = 0;
    removed_reaction(reaction_event(message.id, alice.user_id));
    assert.ok(desktop_notifications.get_notifications().has(message.id.toString()));
    assert.deepEqual(notices.closed_tags, []);
    removed_reaction(reaction_event(message.id, bob.user_id));
    assert.equal(desktop_notifications.get_notifications().size, 0);
    assert.deepEqual(notices.closed_tags, [message.id.toString()]);
    assert.equal(notices.shown_count, 0);
});

test("reactions notify unless the user is watching the message", ({override}) => {
    const notices = stub_notification_api();
    stub_message_content_parsing();
    const message_id = 3700;
    cache_message(message_id);
    const message = message_store.get(message_id);

    function reactions_shown() {
        notices.shown_count = 0;
        received_reaction(reaction_event(message_id, alice.user_id));
        desktop_notifications.close_notification(message_id);
        return notices.shown_count;
    }

    const list_showing_message = {get: () => message};
    const list_showing_other_conversation = {get: () => undefined};

    // Zulip in the background, an overlay covering the feed, or a view that
    // replaces the feed entirely: viewport_is_visible_and_focused is false and
    // the reaction notifies, even with the message in the current list.
    override(unread_ops, "viewport_is_visible_and_focused", () => false);
    override(message_lists, "current", list_showing_message);
    assert.equal(reactions_shown(), 1);

    // Focused and watching the feed, but narrowed to a conversation that does
    // not contain the message: still unseen, so it still notifies.
    override(unread_ops, "viewport_is_visible_and_focused", () => true);
    override(message_lists, "current", list_showing_other_conversation);
    assert.equal(reactions_shown(), 1);

    // No message list at all -- Inbox or Recent conversations -- likewise
    // means the message is not in front of the user.
    override(message_lists, "current", undefined);
    assert.equal(reactions_shown(), 1);

    // Focused, watching the feed, and the message is in it: the reaction
    // appears on the message in front of the user, so we stay quiet.
    override(message_lists, "current", list_showing_message);
    assert.equal(reactions_shown(), 0);
});

test("reaction notification body", ({override}) => {
    // The reacted-to message is always the current user's own, so the body
    // must never render a direct message as "New direct message from <the
    // current user>", the way message notifications do for an incoming DM.
    const notices = stub_notification_api();
    stub_message_content_parsing();

    const my_direct_message = {id: 3100, type: "private", content: "<p>my secret plans</p>"};
    const my_stream_message = my_channel_message(3200);

    function notify_about(message, plain_text_content) {
        // The body is read out of the parsed-HTML container, which zjquery
        // stubs; seed the text that container will report.
        $("<div>").text(plain_text_content);
        notices.last_body = undefined;
        react(message, alice.user_id);
        return notices.last_body;
    }

    // With DM content allowed in notifications, the body is the content of the
    // user's own message, so they can tell which one was reacted to.
    override(user_settings, "pm_content_in_desktop_notifications", true);
    assert.equal(notify_about(my_direct_message, "my secret plans"), "my secret plans");

    // With DM content suppressed, the body says only that there was a
    // reaction. In particular it must not fall back to the message
    // notification wording, "New direct message from <the current user>".
    override(user_settings, "pm_content_in_desktop_notifications", false);
    assert.equal(
        notify_about(my_direct_message, "my secret plans"),
        "translated: New reaction to your direct message.",
    );

    // The setting covers direct messages only, so a reaction to the user's own
    // channel message still shows its content.
    assert.equal(notify_about(my_stream_message, "my channel message"), "my channel message");
});

test("reaction notification from an inaccessible user", ({override}) => {
    // In a realm where users cannot access all other users, a reaction event
    // can name a user this client has no record of, and a cached message gives
    // us no reactions to backfill them from. Notifying must still work,
    // crediting the same "Unknown user" placeholder the message feed uses.
    const notices = stub_notification_api();
    stub_message_content_parsing();
    override(settings_data, "user_can_access_all_other_users", () => false);
    assert.ok(!people.is_known_user_id(inaccessible_user_id));

    // Cache the message, so that we take the path that has no message fetch to
    // add the reacting user for us.
    const message_id = 1900;
    cache_message(message_id);
    received_reaction(reaction_event(message_id, inaccessible_user_id));

    assert.ok(desktop_notifications.get_notifications().has(message_id.toString()));
    assert.equal(notices.last_title, "translated: translated: Unknown user reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${inaccessible_user_id}`);
});

test("received_reactions fetches the messages it needs in one request", ({override}) => {
    // A batch of events -- what a client that has been idle receives when it
    // reconnects, which is exactly when reactions notify -- must cost one
    // request for all the messages it needs, not one per reaction.
    const notices = stub_notification_api();
    stub_message_content_parsing();
    const fetches = [];
    override(channel, "get", (opts) => {
        fetches.push(opts);
    });

    const cached_message_id = 1830;
    cache_message(cached_message_id);
    reaction_notifications.received_reactions([
        added(reaction_event(1810, alice.user_id)),
        added(reaction_event(1820, bob.user_id)),
        added(reaction_event(1810, bob.user_id)),
        // A reaction to someone else's message needs no message at all.
        added({...reaction_event(1840, alice.user_id), message_sender_id: alice.user_id}),
        added(reaction_event(cached_message_id, alice.user_id)),
    ]);
    assert.equal(fetches.length, 1);
    assert.deepEqual(JSON.parse(fetches[0].data.message_ids), [1810, 1820]);

    // The cached message notified without waiting for the request.
    assert.ok(desktop_notifications.get_notifications().has(cached_message_id.toString()));

    fetches[0].success({messages: [raw_message(1810), raw_message(1820)]});
    const notifications = desktop_notifications.get_notifications();
    assert.ok(notifications.has("1810"));
    assert.ok(notifications.has("1820"));
    assert.ok(!notifications.has("1840"));
    // Both of the batch's reactions to 1810 are credited in its notification.
    assert.equal(notices.title_by_tag.get("1810"), "translated: Bob and Alice reacted with 🎉");

    // The response cached those messages, so a later reaction to one of them
    // takes the cached path and notifies without another request.
    received_reaction(reaction_event(1810, cindy.user_id));
    assert.equal(fetches.length, 1);
    assert.equal(notices.last_title, "translated: Cindy and 2 others reacted with 🎉");

    // A message that is gone by the time the request runs -- deleted, say --
    // is simply absent from the response, and is not notified about. Its
    // reactions are no longer pending, so a later reaction to it is fetched
    // afresh rather than being mistaken for one of them.
    received_reaction(reaction_event(1850, alice.user_id));
    assert.equal(fetches.length, 2);
    fetches[1].success({messages: []});
    assert.ok(!desktop_notifications.get_notifications().has("1850"));

    received_reaction(reaction_event(1850, alice.user_id));
    assert.equal(fetches.length, 3);
    fetches[2].success({messages: [raw_message(1850)]});
    assert.ok(desktop_notifications.get_notifications().has("1850"));

    // A failed request shows nothing, and clears the whole batch's pending
    // state, so later reactions to those messages are fetched again.
    reaction_notifications.received_reactions([
        added(reaction_event(1880, alice.user_id)),
        added(reaction_event(1890, alice.user_id)),
    ]);
    assert.equal(fetches.length, 4);
    fetches[3].error();
    assert.ok(!desktop_notifications.get_notifications().has("1880"));

    received_reaction(reaction_event(1880, alice.user_id));
    assert.equal(fetches.length, 5);
    fetches[4].success({messages: [raw_message(1880)]});
    assert.ok(desktop_notifications.get_notifications().has("1880"));
});

test("a reaction retracted in the same batch does not notify", ({disallow}) => {
    // Reacting and then unreacting while the user is away is not activity
    // worth a notification or a sound. An add that a later event in the same
    // batch retracts is therefore dropped before it is acted on -- for a
    // cached message just as much as for one we have to fetch.
    const notices = stub_notification_api();
    stub_message_content_parsing();
    // Every reaction here is to a message we have cached, so nothing in this
    // test may reach the server.
    disallow(channel, "get");
    const message_id = 3600;
    cache_message(message_id);

    // The retraction that follows the add drops it, so nothing is shown.
    reaction_notifications.received_reactions([
        added(reaction_event(message_id, alice.user_id)),
        retracted(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(notices.shown_count, 0);
    assert.equal(desktop_notifications.get_notifications().size, 0);

    // A retraction *before* the add is the opposite sequence: the user reacted
    // again, which is new activity and does notify.
    reaction_notifications.received_reactions([
        retracted(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(notices.shown_count, 1);
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");

    // Retracting a different reaction leaves the added one to notify, and the
    // title credits only the reaction that survived the batch.
    notices.shown_count = 0;
    reaction_notifications.received_reactions([
        added(reaction_event(message_id, alice.user_id, thumbs_up)),
        retracted(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(notices.shown_count, 1);
    assert.equal(notices.last_title, "translated: Alice reacted with 👍");
});

test("a reaction re-added within one batch is credited as the newest", ({disallow, override}) => {
    // A user who unreacts and reacts again is the newest reactor, so the
    // notification must credit and picture them rather than whoever reacted
    // in between. Recording a reaction has to remove it from the tracked set
    // before adding it back for that to hold: setting a key a Map already has
    // leaves it in its original position.
    const notices = stub_notification_api();
    stub_message_content_parsing();
    // The message is cached, so nothing here may reach the server.
    disallow(channel, "get");
    let message_id = 3800;
    cache_message(message_id);

    reaction_notifications.received_reactions([
        added(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, bob.user_id)),
        retracted(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, alice.user_id)),
    ]);

    assert.equal(notices.last_title, "translated: Alice and Bob reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${alice.user_id}`);
    // Alice's reaction is notified about once, for the add that survived the
    // batch, rather than once for each of her two adds.
    assert.equal(notices.shown_count, 2);

    reaction_notifications.received_reactions([
        retracted(reaction_event(message_id, bob.user_id)),
        added(reaction_event(message_id, bob.user_id)),
    ]);

    assert.equal(notices.last_title, "translated: Bob and Alice reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${bob.user_id}`);

    // A batch against a message we have to fetch must reach the same result
    // as one against a message we have cached.
    const fetches = [];
    override(channel, "get", (opts) => {
        fetches.push(opts);
    });
    message_id = 3900;
    notices.shown_count = 0;

    reaction_notifications.received_reactions([
        added(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, bob.user_id)),
        retracted(reaction_event(message_id, alice.user_id)),
        added(reaction_event(message_id, alice.user_id)),
    ]);
    assert.equal(fetches.length, 1);

    fetches[0].success({messages: [raw_message(message_id)]});
    assert.equal(notices.shown_count, 2);
    assert.equal(notices.last_title, "translated: Alice and Bob reacted with 🎉");
    assert.equal(notices.last_icon, `/avatar/${alice.user_id}`);
});

test("pending reaction notifications are scoped to their fetch", ({override}) => {
    // The pending notifications for an in-flight message fetch belong to that
    // request alone. Sharing them across requests would let a request that
    // fails cancel a later request's still-live reaction, and would let a
    // batch with nothing left to notify about mistake another request's
    // pending reactions for its own and fetch anyway.
    const notices = stub_notification_api();
    stub_message_content_parsing();
    const fetches = [];
    override(channel, "get", (opts) => {
        fetches.push(opts);
    });

    // A reaction retracted by a later event in the same batch leaves nothing
    // to notify about, so its message is not requested at all.
    reaction_notifications.received_reactions([
        added(reaction_event(1860, alice.user_id)),
        retracted(reaction_event(1860, alice.user_id)),
    ]);
    assert.equal(fetches.length, 0);

    // The rest of such a batch is still fetched, and only the surviving
    // reaction notifies.
    reaction_notifications.received_reactions([
        added(reaction_event(1870, alice.user_id)),
        added(reaction_event(1870, bob.user_id)),
        retracted(reaction_event(1870, bob.user_id)),
    ]);
    assert.equal(fetches.length, 1);
    assert.deepEqual(JSON.parse(fetches[0].data.message_ids), [1870]);
    fetches[0].success({messages: [raw_message(1870)]});
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");

    // Retracting a reaction while its message fetch is in flight must not
    // notify once the fetch lands. Nothing would dismiss such a notification:
    // no reaction remains for a later removal to clear.
    received_reaction(reaction_event(1880, alice.user_id));
    removed_reaction(reaction_event(1880, alice.user_id));
    notices.last_title = undefined;
    fetches[1].success({messages: [raw_message(1880)]});
    assert.ok(!desktop_notifications.get_notifications().has("1880"));
    assert.equal(notices.last_title, undefined);

    // That fetch still cached the message, so a fresh reaction to it notifies
    // without another fetch.
    received_reaction(reaction_event(1880, alice.user_id));
    assert.equal(fetches.length, 2);
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");

    // A reaction retracted mid-fetch only cancels itself; a different
    // reactor's reaction to the same message still notifies.
    received_reaction(reaction_event(1890, alice.user_id));
    received_reaction(reaction_event(1890, bob.user_id));
    assert.equal(fetches.length, 4);
    removed_reaction(reaction_event(1890, alice.user_id));
    notices.last_title = undefined;
    fetches[2].success({messages: [raw_message(1890)]});
    assert.equal(notices.last_title, undefined);
    fetches[3].success({messages: [raw_message(1890)]});
    assert.equal(notices.last_title, "translated: Bob reacted with 🎉");

    // The same reaction added, retracted, and added again while the first
    // fetch is still in flight is pending on the second request. The first
    // request failing must not cancel it.
    received_reaction(reaction_event(1900, alice.user_id));
    removed_reaction(reaction_event(1900, alice.user_id));
    received_reaction(reaction_event(1900, alice.user_id));
    assert.equal(fetches.length, 6);
    fetches[4].error();
    notices.last_title = undefined;
    fetches[5].success({messages: [raw_message(1900)]});
    assert.equal(notices.last_title, "translated: Alice reacted with 🎉");

    // A batch whose only reaction to an uncached message is retracted within
    // that same batch has nothing left to notify about, so it must not fetch
    // the message, even while another request for that same message is
    // outstanding.
    received_reaction(reaction_event(1910, alice.user_id));
    assert.equal(fetches.length, 7);
    reaction_notifications.received_reactions([
        added(reaction_event(1910, bob.user_id)),
        retracted(reaction_event(1910, bob.user_id)),
    ]);
    assert.equal(fetches.length, 7);

    // Let the outstanding request finish, so it does not stay registered.
    fetches[6].error();
});

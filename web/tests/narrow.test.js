"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {page_params, realm} = require("./lib/zpage_params");

const hash_util = zrequire("hash_util");
const compose_state = zrequire("compose_state");
const narrow_banner = zrequire("narrow_banner");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const {Filter} = zrequire("../src/filter");
const narrow = zrequire("narrow");
const narrow_title = zrequire("narrow_title");
const settings_config = zrequire("settings_config");
const recent_view_util = zrequire("recent_view_util");
const inbox_util = zrequire("inbox_util");
const message_lists = zrequire("message_lists");

mock_esm("../src/compose_banner", {
    clear_search_view_banner() {},
});
const compose_pm_pill = mock_esm("../src/compose_pm_pill");
mock_esm("../src/spectators", {
    login_to_access() {},
});

function empty_narrow_html(title, html, search_data) {
    const opts = {
        title,
        html,
        search_data,
    };
    return require("../templates/empty_feed_notice.hbs")(opts);
}

function set_filter(terms) {
    terms = terms.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    message_lists.set_current({
        data: {
            filter: new Filter(terms),
        },
    });
}

const me = {
    email: "me@example.com",
    user_id: 5,
    full_name: "Me Myself",
};

const alice = {
    email: "alice@example.com",
    user_id: 23,
    full_name: "Alice Smith",
};

const ray = {
    email: "ray@example.com",
    user_id: 22,
    full_name: "Raymond",
};

const bot = {
    email: "bot@example.com",
    user_id: 25,
    full_name: "Example Bot",
    is_bot: true,
};

run_test("empty_narrow_html", ({mock_template}) => {
    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    let actual_html = empty_narrow_html("This is a title", "<h1> This is the html </h1>");
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
    <div class="empty-feed-notice-description">
            <h1> This is the html </h1>
    </div>
</div>
`,
    );

    const search_data_with_all_search_types = {
        topic_query: "test",
        stream_query: "new",
        has_stop_word: true,
        query_words: [
            {query_word: "search", is_stop_word: false},
            {query_word: "a", is_stop_word: true},
        ],
    };
    actual_html = empty_narrow_html(
        "This is a title",
        undefined,
        search_data_with_all_search_types,
    );
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
    <div class="empty-feed-notice-description">
            Some common words were excluded from your search. <br/>You searched for:
            <span>stream: new</span>
            <span>topic: test</span>
                <span>search</span>
                <del>a</del>
    </div>
</div>
`,
    );

    const search_data_with_stream_without_stop_words = {
        has_stop_word: false,
        stream_query: "hello world",
        query_words: [{query_word: "searchA", is_stop_word: false}],
    };
    actual_html = empty_narrow_html(
        "This is a title",
        undefined,
        search_data_with_stream_without_stop_words,
    );
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
    <div class="empty-feed-notice-description">
            You searched for:
            <span>stream: hello world</span>
                <span>searchA</span>
    </div>
</div>
`,
    );

    const search_data_with_topic_without_stop_words = {
        has_stop_word: false,
        topic_query: "hello",
        query_words: [{query_word: "searchB", is_stop_word: false}],
    };
    actual_html = empty_narrow_html(
        "This is a title",
        undefined,
        search_data_with_topic_without_stop_words,
    );
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
    <div class="empty-feed-notice-description">
            You searched for:
            <span>topic: hello</span>
                <span>searchB</span>
    </div>
</div>
`,
    );
});

run_test("urls", () => {
    people.add_active_user(ray);
    people.add_active_user(alice);
    people.add_active_user(me);
    people.initialize_current_user(me.user_id);

    let url = hash_util.pm_with_url(ray.email);
    assert.equal(url, "#narrow/dm/22-Raymond");

    url = hash_util.huddle_with_url("22,23");
    assert.equal(url, "#narrow/dm/22,23-group");

    url = hash_util.by_sender_url(ray.email);
    assert.equal(url, "#narrow/sender/22-Raymond");

    let emails = hash_util.decode_operand("dm", "22,23-group");
    assert.equal(emails, "alice@example.com,ray@example.com");

    emails = hash_util.decode_operand("dm", "5,22,23-group");
    assert.equal(emails, "alice@example.com,ray@example.com");

    emails = hash_util.decode_operand("dm", "5-group");
    assert.equal(emails, "me@example.com");

    // Even though we renamed "pm-with" to "dm", preexisting
    // links/URLs with "pm-with" operator are decoded correctly.
    emails = hash_util.decode_operand("pm-with", "22,23-group");
    assert.equal(emails, "alice@example.com,ray@example.com");

    emails = hash_util.decode_operand("pm-with", "5,22,23-group");
    assert.equal(emails, "alice@example.com,ray@example.com");

    emails = hash_util.decode_operand("pm-with", "5-group");
    assert.equal(emails, "me@example.com");
});

run_test("show_empty_narrow_message", ({mock_template}) => {
    realm.stop_words = [];

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    message_lists.set_current(undefined);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    // for non-existent or private stream
    set_filter([["stream", "Foo"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This channel does not exist or is private."),
    );

    // for non-subbed public stream
    stream_data.add_sub({name: "ROME", stream_id: 99});
    set_filter([["stream", "Rome"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    // for non-web-public stream for spectator
    page_params.is_spectator = true;
    set_filter([["stream", "Rome"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "",
            'translated HTML: This is not a <a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">publicly accessible</a> conversation.',
        ),
    );

    set_filter([
        ["stream", "Rome"],
        ["topic", "foo"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "",
            'translated HTML: This is not a <a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">publicly accessible</a> conversation.',
        ),
    );

    // for web-public stream for spectator
    stream_data.add_sub({name: "web-public-stream", stream_id: 1231, is_web_public: true});
    set_filter([
        ["stream", "web-public-stream"],
        ["topic", "foo"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: There are no messages here."),
    );
    page_params.is_spectator = false;

    set_filter([["is", "starred"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no starred messages.",
            'translated HTML: Learn more about starring messages <a target="_blank" rel="noopener noreferrer" href="/help/star-a-message">here</a>.',
        ),
    );

    set_filter([["is", "mentioned"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You haven't been mentioned yet!",
            'translated HTML: Learn more about mentions <a target="_blank" rel="noopener noreferrer" href="/help/mention-a-user-or-group">here</a>.',
        ),
    );

    // organization has disabled sending direct messages
    realm.realm_private_message_policy =
        settings_config.private_message_policy_values.disabled.code;
    set_filter([["is", "dm"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You are not allowed to send direct messages in this organization.",
        ),
    );

    // sending direct messages enabled
    realm.realm_private_message_policy =
        settings_config.private_message_policy_values.by_anyone.code;
    set_filter([["is", "dm"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages yet!",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    set_filter([["is", "unread"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no unread messages!"),
    );

    set_filter([["is", "resolved"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No topics are marked as resolved."),
    );

    // organization has disabled sending direct messages
    realm.realm_private_message_policy =
        settings_config.private_message_policy_values.disabled.code;

    // prioritize information about invalid user(s) in narrow/search
    set_filter([["dm", ["Yo"]]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    people.add_active_user(alice);
    set_filter([["dm", ["alice@example.com", "Yo"]]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: One or more of these users do not exist!"),
    );

    set_filter([["dm", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You are not allowed to send direct messages in this organization.",
        ),
    );

    // direct messages with a bot are possible even though
    // the organization has disabled sending direct messages
    people.add_active_user(bot);
    set_filter([["dm", "bot@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with Example Bot yet.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // group direct messages with bots are not possible when
    // sending direct messages is disabled
    set_filter([["dm", bot.email + "," + alice.email]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You are not allowed to send direct messages in this organization.",
        ),
    );

    // sending direct messages enabled
    realm.realm_private_message_policy =
        settings_config.private_message_policy_values.by_anyone.code;
    set_filter([["dm", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with Alice Smith yet.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
    set_filter([["dm", me.email]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have not sent any direct messages to yourself yet!",
            "translated HTML: Use this space for personal notes, or to test out Zulip features.",
        ),
    );

    set_filter([["dm", me.email + "," + alice.email]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with these users yet.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // organization has disabled sending direct messages
    realm.realm_private_message_policy =
        settings_config.private_message_policy_values.disabled.code;

    // prioritize information about invalid user in narrow/search
    set_filter([["dm-including", ["Yo"]]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    set_filter([["dm-including", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You are not allowed to send direct messages in this organization.",
        ),
    );

    // direct messages with a bot are possible even though
    // the organization has disabled sending direct messages
    set_filter([["dm-including", "bot@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages including Example Bot yet."),
    );

    // sending direct messages enabled
    realm.realm_private_message_policy =
        settings_config.private_message_policy_values.by_anyone.code;
    set_filter([["dm-including", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages including Alice Smith yet."),
    );

    set_filter([["dm-including", me.email]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You don't have any direct message conversations yet."),
    );

    set_filter([["sender", "ray@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You haven't received any messages sent by Raymond yet."),
    );

    set_filter([["sender", "sinwar@example.com"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    set_filter([
        ["sender", "alice@example.com"],
        ["stream", "Rome"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results."),
    );

    set_filter([["is", "invalid"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    const my_stream = {
        name: "my stream",
        stream_id: 103,
    };
    stream_data.add_sub(my_stream);
    stream_data.subscribe_myself(my_stream);

    set_filter([["stream", "my stream"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    set_filter([["stream", ""]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This channel does not exist or is private."),
    );
});

run_test("show_empty_narrow_message_with_search", ({mock_template}) => {
    realm.stop_words = [];

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    message_lists.set_current(undefined);
    set_filter([["search", "grail"]]);
    narrow_banner.show_empty_narrow_message();
    assert.match($(".empty_feed_notice_main").html(), /<span>grail<\/span>/);
});

run_test("hide_empty_narrow_message", () => {
    narrow_banner.hide_empty_narrow_message();
    assert.equal($(".empty_feed_notice").text(), "never-been-set");
});

run_test("show_search_stopwords", ({mock_template}) => {
    realm.stop_words = ["what", "about"];

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    const expected_search_data = {
        has_stop_word: true,
        query_words: [
            {query_word: "what", is_stop_word: true},
            {query_word: "about", is_stop_word: true},
            {query_word: "grail", is_stop_word: false},
        ],
    };
    message_lists.set_current(undefined);
    set_filter([["search", "what about grail"]]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results.", undefined, expected_search_data),
    );

    const expected_stream_search_data = {
        has_stop_word: true,
        stream_query: "streamA",
        query_words: [
            {query_word: "what", is_stop_word: true},
            {query_word: "about", is_stop_word: true},
            {query_word: "grail", is_stop_word: false},
        ],
    };
    set_filter([
        ["stream", "streamA"],
        ["search", "what about grail"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results.", undefined, expected_stream_search_data),
    );

    const expected_stream_topic_search_data = {
        has_stop_word: true,
        stream_query: "streamA",
        topic_query: "topicA",
        query_words: [
            {query_word: "what", is_stop_word: true},
            {query_word: "about", is_stop_word: true},
            {query_word: "grail", is_stop_word: false},
        ],
    };
    set_filter([
        ["stream", "streamA"],
        ["topic", "topicA"],
        ["search", "what about grail"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            undefined,
            expected_stream_topic_search_data,
        ),
    );
});

run_test("show_invalid_narrow_message", ({mock_template}) => {
    message_lists.set_current(undefined);
    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    stream_data.add_sub({name: "streamA", stream_id: 88});
    stream_data.add_sub({name: "streamB", stream_id: 77});

    set_filter([
        ["stream", "streamA"],
        ["stream", "streamB"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated HTML: <p>You are searching for messages that belong to more than one channel, which is not possible.</p>",
        ),
    );

    set_filter([
        ["topic", "topicA"],
        ["topic", "topicB"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated HTML: <p>You are searching for messages that belong to more than one topic, which is not possible.</p>",
        ),
    );

    people.add_active_user(ray);
    people.add_active_user(alice);

    set_filter([
        ["sender", "alice@example.com"],
        ["sender", "ray@example.com"],
    ]);
    narrow_banner.show_empty_narrow_message();
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated HTML: <p>You are searching for messages that are sent by more than one person, which is not possible.</p>",
        ),
    );
});

run_test("narrow_to_compose_target errors", ({disallow_rewire}) => {
    disallow_rewire(narrow, "activate");

    // No-op when not composing.
    compose_state.set_message_type(undefined);
    narrow.to_compose_target();

    // No-op when empty stream.
    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    narrow.to_compose_target();
});

run_test("narrow_to_compose_target streams", ({override_rewire}) => {
    const args = {called: false};
    override_rewire(narrow, "activate", (terms, opts) => {
        args.terms = terms;
        args.opts = opts;
        args.called = true;
    });

    compose_state.set_message_type("stream");
    stream_data.add_sub({name: "ROME", stream_id: 99});
    compose_state.set_stream_id(99);

    // Test with existing topic
    compose_state.topic("one");
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.equal(args.opts.trigger, "narrow_to_compose_target");
    assert.deepEqual(args.terms, [
        {operator: "channel", operand: "ROME"},
        {operator: "topic", operand: "one"},
    ]);

    // Test with new topic
    compose_state.topic("four");
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [
        {operator: "channel", operand: "ROME"},
        {operator: "topic", operand: "four"},
    ]);

    // Test with blank topic
    compose_state.topic("");
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "channel", operand: "ROME"}]);

    // Test with no topic
    compose_state.topic(undefined);
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "channel", operand: "ROME"}]);
});

run_test("narrow_to_compose_target direct messages", ({override, override_rewire}) => {
    const args = {called: false};
    override_rewire(narrow, "activate", (terms, opts) => {
        args.terms = terms;
        args.opts = opts;
        args.called = true;
    });

    let emails;
    override(compose_pm_pill, "get_emails", () => emails);

    compose_state.set_message_type("private");
    people.add_active_user(ray);
    people.add_active_user(alice);
    people.add_active_user(me);

    // Test with valid person
    emails = "alice@example.com";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "dm", operand: "alice@example.com"}]);

    // Test with valid persons
    emails = "alice@example.com,ray@example.com";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "dm", operand: "alice@example.com,ray@example.com"}]);

    // Test with some invalid persons
    emails = "alice@example.com,random,ray@example.com";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);

    // Test with all invalid persons
    emails = "alice,random,ray";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);

    // Test with no persons
    emails = "";
    args.called = false;
    narrow.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);
});

run_test("narrow_compute_title", () => {
    // Only tests cases where the narrow title is different from the filter title.
    let filter;

    // Recent conversations & Inbox have `undefined` filter.
    filter = undefined;
    recent_view_util.set_visible(true);
    inbox_util.set_visible(false);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Recent conversations");

    recent_view_util.set_visible(false);
    inbox_util.set_visible(true);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Inbox");

    inbox_util.set_visible(false);
    filter = new Filter([{operator: "in", operand: "home"}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Combined feed");

    // Search & uncommon narrows
    filter = new Filter([{operator: "search", operand: "potato"}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Search results");

    filter = new Filter([{operator: "sender", operand: "me"}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Messages sent by you");

    // Stream narrows
    const sub = {
        name: "Foo",
        stream_id: 43,
    };
    stream_data.add_sub(sub);

    filter = new Filter([
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ]);
    assert.equal(narrow_title.compute_narrow_title(filter), "#Foo > bar");

    filter = new Filter([{operator: "stream", operand: "foo"}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "#Foo");

    filter = new Filter([{operator: "stream", operand: "Elephant"}]);
    assert.equal(
        narrow_title.compute_narrow_title(filter),
        "translated: Unknown channel #Elephant",
    );

    // Direct messages with narrows
    const joe = {
        email: "joe@example.com",
        user_id: 31,
        full_name: "joe",
    };
    people.add_active_user(joe);

    filter = new Filter([{operator: "dm", operand: "joe@example.com"}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "joe");

    filter = new Filter([{operator: "dm", operand: "joe@example.com,sally@doesnotexist.com"}]);
    blueslip.expect("warn", "Unknown emails");
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Invalid users");

    blueslip.reset();
    filter = new Filter([{operator: "dm", operand: "sally@doesnotexist.com"}]);
    blueslip.expect("warn", "Unknown emails");
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Invalid user");
});

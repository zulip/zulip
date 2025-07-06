"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire, set_global} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const hash_util = zrequire("hash_util");
const compose_state = zrequire("compose_state");
const narrow_banner = zrequire("narrow_banner");
const people = zrequire("people");
const stream_data = zrequire("stream_data");
const {Filter} = zrequire("../src/filter");
const message_view = zrequire("message_view");
const narrow_title = zrequire("narrow_title");
const recent_view_util = zrequire("recent_view_util");
const inbox_util = zrequire("inbox_util");
const {set_current_user, set_realm} = zrequire("state_data");
const user_groups = zrequire("user_groups");
const {initialize_user_settings} = zrequire("user_settings");
const {MessageList} = zrequire("message_list");
const {MessageListData} = zrequire("message_list_data");

set_current_user({});
const realm = {};
set_realm(realm);
initialize_user_settings({user_settings: {}});

set_global("document", "document-stub");
const message_lists = mock_esm("../src/message_lists");
function MessageListView() {
    return {
        maybe_rerender: noop,
        append: noop,
        prepend: noop,
    };
}
mock_esm("../src/message_list_view", {
    MessageListView,
});
mock_esm("../src/compose_banner", {
    clear_errors() {},
    clear_search_view_banner() {},
});
const compose_pm_pill = mock_esm("../src/compose_pm_pill");
mock_esm("../src/settings_data", {
    user_can_access_all_other_users: () => true,
    user_has_permission_for_group_setting: () => true,
});
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
    return new Filter(terms);
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

const nobody = {
    name: "role:nobody",
    id: 1,
    members: new Set([]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};
const everyone = {
    name: "role:everyone",
    id: 2,
    members: new Set([5]),
    is_system_group: true,
    direct_subgroup_ids: new Set([]),
};

user_groups.initialize({realm_user_groups: [nobody, everyone]});

run_test("empty_narrow_html", ({mock_template}) => {
    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    // Title only
    let actual_html = empty_narrow_html("This is a title", undefined, undefined);
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
</div>
`,
    );

    // Title and html
    actual_html = empty_narrow_html("This is a title", "<h1> This is the html </h1>", undefined);
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

    // Title and search data
    const search_data_with_stop_word = {
        has_stop_word: true,
        query_words: [
            {query_word: "a", is_stop_word: true},
            {query_word: "search", is_stop_word: false},
        ],
    };
    actual_html = empty_narrow_html("This is a title", undefined, search_data_with_stop_word);
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
        <div class="empty-feed-notice-description">
            Common words were excluded from your search: <br/>
                <del>a</del>
                <span class="search-query-word">search</span>
        </div>
</div>
`,
    );

    const search_data_with_stop_words = {
        has_stop_word: true,
        query_words: [
            {query_word: "a", is_stop_word: true},
            {query_word: "search", is_stop_word: false},
            {query_word: "and", is_stop_word: true},
            {query_word: "return", is_stop_word: false},
        ],
    };
    actual_html = empty_narrow_html("This is a title", undefined, search_data_with_stop_words);
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
        <div class="empty-feed-notice-description">
            Common words were excluded from your search: <br/>
                <del>a</del>
                <span class="search-query-word">search</span>
                <del>and</del>
                <span class="search-query-word">return</span>
        </div>
</div>
`,
    );

    const search_data_without_stop_words = {
        has_stop_word: false,
        query_words: [{query_word: "search", is_stop_word: false}],
    };
    actual_html = empty_narrow_html("This is a title", undefined, search_data_without_stop_words);
    assert.equal(
        actual_html,
        `<div class="empty_feed_notice">
    <h4 class="empty-feed-notice-title"> This is a title </h4>
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

    url = hash_util.direct_message_group_with_url("22,23");
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

run_test("show_empty_narrow_message", ({mock_template, override}) => {
    override(realm, "stop_words", []);

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    // for empty combined feed
    let current_filter = new Filter([{operator: "in", operand: "home"}]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages in your combined feed.",
            'translated HTML: Would you like to <a href="#narrow/channels/public">view messages in all public channels</a>?',
        ),
    );

    // for non-existent or private stream
    current_filter = set_filter([["stream", "999"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: This channel doesn't exist, or you are not allowed to view it.",
        ),
    );

    current_filter = set_filter([
        ["stream", "999"],
        ["topic", "foo"],
        ["near", "99"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: This channel doesn't exist, or you are not allowed to view it.",
        ),
    );

    // for non-subbed public stream
    const rome_id = 99;
    stream_data.add_sub({name: "ROME", stream_id: rome_id});
    current_filter = set_filter([["stream", rome_id.toString()]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    // for non-web-public stream for spectator
    page_params.is_spectator = true;
    current_filter = set_filter([["stream", rome_id.toString()]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "",
            'translated HTML: This is not a <a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">publicly accessible</a> conversation.',
        ),
    );

    current_filter = set_filter([
        ["stream", rome_id.toString()],
        ["topic", "foo"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "",
            'translated HTML: This is not a <a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">publicly accessible</a> conversation.',
        ),
    );

    // for web-public stream for spectator
    const web_public_id = 1231;
    stream_data.add_sub({name: "web-public-stream", stream_id: web_public_id, is_web_public: true});
    current_filter = set_filter([
        ["stream", web_public_id.toString()],
        ["topic", "foo"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: There are no messages here."),
    );
    page_params.is_spectator = false;

    current_filter = set_filter([["is", "starred"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no starred messages.",
            'translated HTML: Starring messages is a good way to keep track of important messages, such as tasks you need to go back to, or useful references. To star a message, hover over a message and click the <i class="zulip-icon zulip-icon-star" aria-hidden="true"></i>. <a target="_blank" rel="noopener noreferrer" href="/help/star-a-message">Learn more</a>',
        ),
    );

    current_filter = set_filter([["is", "mentioned"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: This view will show messages where you are mentioned.",
            'translated HTML: To call attention to a message, you can mention a user, a group, topic participants, or all subscribers to a channel. Type @ in the compose box, and choose who you\'d like to mention from the list of suggestions. <a target="_blank" rel="noopener noreferrer" href="/help/mention-a-user-or-group">Learn more</a>',
        ),
    );

    override(realm, "realm_direct_message_permission_group", everyone.id);
    override(realm, "realm_direct_message_initiator_group", everyone.id);
    current_filter = set_filter([["is", "dm"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages yet!",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    current_filter = set_filter([["is", "unread"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no unread messages!"),
    );

    current_filter = set_filter([["is", "resolved"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No topics are marked as resolved."),
    );

    current_filter = set_filter([["is", "followed"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You aren't following any topics."),
    );

    current_filter = set_filter([["is", "muted"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no messages in muted topics and channels."),
    );
    // organization has disabled sending direct messages
    override(realm, "realm_direct_message_permission_group", nobody.id);

    // prioritize information about invalid user(s) in narrow/search
    current_filter = set_filter([["dm", ["Yo"]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    people.add_active_user(alice);
    current_filter = set_filter([["dm", ["alice@example.com", "Yo"]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: One or more of these users do not exist!"),
    );

    current_filter = set_filter([["dm", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: Direct messages are disabled in this organization.",
            'translated HTML: <a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">Learn more.</a>',
        ),
    );

    // direct messages with a bot are possible even though
    // the organization has disabled sending direct messages
    people.add_active_user(bot);
    current_filter = set_filter([["dm", "bot@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with Example Bot yet.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // group direct messages with bots are not possible when
    // sending direct messages is disabled
    current_filter = set_filter([["dm", bot.email + "," + alice.email]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: Direct messages are disabled in this organization.",
            'translated HTML: <a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">Learn more.</a>',
        ),
    );

    // sending direct messages enabled
    override(realm, "realm_direct_message_permission_group", everyone.id);
    current_filter = set_filter([["dm", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with Alice Smith yet.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // sending direct messages to deactivated user
    override(realm, "realm_direct_message_permission_group", everyone.id);
    people.deactivate(alice);
    current_filter = set_filter([["dm", alice.email]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages with Alice Smith."),
    );
    people.add_active_user(alice);

    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
    current_filter = set_filter([["dm", me.email]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have not sent any direct messages to yourself yet!",
            "translated HTML: Use this space for personal notes, or to test out Zulip features.",
        ),
    );

    current_filter = set_filter([["dm", me.email + "," + alice.email]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with these users yet.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // group dm with a deactivated user
    people.deactivate(alice);
    current_filter = set_filter([["dm", ray.email + "," + alice.email]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages with these users."),
    );
    people.add_active_user(alice);

    // organization has disabled sending direct messages
    override(realm, "realm_direct_message_permission_group", nobody.id);

    // prioritize information about invalid user in narrow/search
    current_filter = set_filter([["dm-including", ["Yo"]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    current_filter = set_filter([["dm-including", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: Direct messages are disabled in this organization.",
            'translated HTML: <a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">Learn more.</a>',
        ),
    );

    // direct messages with a bot are possible even though
    // the organization has disabled sending direct messages
    current_filter = set_filter([["dm-including", "bot@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages including Example Bot yet."),
    );

    // sending direct messages enabled
    override(realm, "realm_direct_message_permission_group", everyone.id);
    override(realm, "realm_direct_message_permission_group", everyone.id);
    current_filter = set_filter([["dm-including", "alice@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages including Alice Smith yet."),
    );

    current_filter = set_filter([["dm-including", me.email]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You don't have any direct message conversations yet."),
    );

    current_filter = set_filter([["sender", "ray@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You haven't received any messages sent by Raymond yet."),
    );

    current_filter = set_filter([["sender", "sinwar@example.com"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    current_filter = set_filter([
        ["sender", "alice@example.com"],
        ["stream", rome_id.toString()],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results."),
    );

    current_filter = set_filter([["is", "invalid"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    const my_stream_id = 103;
    const my_stream = {
        name: "my stream",
        stream_id: my_stream_id,
    };
    stream_data.add_sub(my_stream);
    stream_data.subscribe_myself(my_stream);
    current_filter = set_filter([["stream", my_stream_id.toString()]]);
    const list = new MessageList({
        data: new MessageListData({
            excludes_muted_topics: false,
            filter: current_filter,
        }),
    });
    message_lists.current = list;
    message_lists.current.visibly_empty = () => true;

    // There are muted topics in the channel.
    message_lists.current.empty = () => false;
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have muted all the topics in this channel.",
            'translated HTML: To view a muted topic, click <b>show all topics</b> in the left sidebar, and select one from the list. <a target="_blank" rel="noopener noreferrer" href="/help/mute-a-topic">Learn more</a>',
        ),
    );
    // There are no muted topics in the channel.
    message_lists.current.empty = () => true;
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated HTML: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );
    // The channel does not exist.
    current_filter = set_filter([["stream", ""]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: This channel doesn't exist, or you are not allowed to view it.",
        ),
    );

    current_filter = set_filter([
        ["has", "reaction"],
        ["sender", "me"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: None of your messages have emoji reactions yet.",
            'translated HTML: Learn more about emoji reactions <a target="_blank" rel="noopener noreferrer" href="/help/emoji-reactions">here</a>.',
        ),
    );
});

run_test("show_empty_narrow_message_with_search", ({mock_template, override}) => {
    override(realm, "stop_words", []);

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    const current_filter = set_filter([["search", "grail"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results."),
    );
});

run_test("hide_empty_narrow_message", () => {
    narrow_banner.hide_empty_narrow_message();
    assert.equal($(".empty_feed_notice").text(), "never-been-set");
});

run_test("show_search_stopwords", ({mock_template, override}) => {
    override(realm, "stop_words", ["what", "about"]);

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    const expected_search_data = {
        has_stop_word: true,
        query_words: [
            {query_word: "what", is_stop_word: true},
            {query_word: "about", is_stop_word: true},
            {query_word: "grail", is_stop_word: false},
        ],
    };
    let current_filter = set_filter([["search", "what about grail"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results.", undefined, expected_search_data),
    );

    const streamA_id = 88;
    stream_data.add_sub({name: "streamA", stream_id: streamA_id});
    current_filter = set_filter([
        ["stream", streamA_id.toString()],
        ["search", "what about grail"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results.", undefined, expected_search_data),
    );

    current_filter = set_filter([
        ["stream", streamA_id.toString()],
        ["topic", "topicA"],
        ["search", "what about grail"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: No search results.", undefined, expected_search_data),
    );
});

run_test("show_invalid_narrow_message", ({mock_template}) => {
    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    const streamA_id = 88;
    const streamB_id = 77;
    stream_data.add_sub({name: "streamA", stream_id: streamA_id});
    stream_data.add_sub({name: "streamB", stream_id: streamB_id});

    let current_filter = set_filter([
        ["stream", streamA_id.toString()],
        ["stream", streamB_id.toString()],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated HTML: <p>You are searching for messages that belong to more than one channel, which is not possible.</p>",
        ),
    );

    current_filter = set_filter([
        ["topic", "topicA"],
        ["topic", "topicB"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated HTML: <p>You are searching for messages that belong to more than one topic, which is not possible.</p>",
        ),
    );

    people.add_active_user(ray);
    people.add_active_user(alice);

    current_filter = set_filter([
        ["sender", "alice@example.com"],
        ["sender", "ray@example.com"],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated HTML: <p>You are searching for messages that are sent by more than one person, which is not possible.</p>",
        ),
    );
});

run_test("narrow_to_compose_target errors", ({disallow_rewire}) => {
    disallow_rewire(message_view, "show");

    // No-op when not composing.
    compose_state.set_message_type(undefined);
    message_view.to_compose_target();

    // No-op when empty stream.
    compose_state.set_message_type("stream");
    compose_state.set_stream_id("");
    message_view.to_compose_target();
});

run_test("narrow_to_compose_target streams", ({override, override_rewire}) => {
    const args = {called: false};
    override_rewire(message_view, "show", (terms, opts) => {
        args.terms = terms;
        args.opts = opts;
        args.called = true;
    });

    compose_state.set_message_type("stream");
    const rome_id = 99;
    stream_data.add_sub({name: "ROME", stream_id: rome_id, topics_policy: "inherit"});
    compose_state.set_stream_id(99);

    // Test with existing topic
    compose_state.topic("one");
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.equal(args.opts.trigger, "narrow_to_compose_target");
    assert.deepEqual(args.terms, [
        {operator: "channel", operand: rome_id.toString()},
        {operator: "topic", operand: "one"},
    ]);

    // Test with new topic
    compose_state.topic("four");
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [
        {operator: "channel", operand: rome_id.toString()},
        {operator: "topic", operand: "four"},
    ]);

    // Test with blank topic, with realm_topics_policy
    override(realm, "realm_topics_policy", "disable_empty_topic");
    compose_state.topic("");
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "channel", operand: rome_id.toString()}]);

    // Test with blank topic, without realm_topics_policy
    override(realm, "realm_topics_policy", "allow_empty_topic");
    compose_state.topic("");
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [
        {operator: "channel", operand: rome_id.toString()},
        {operator: "topic", operand: ""},
    ]);

    // Test with no topic, with realm mandatory topics
    override(realm, "realm_topics_policy", "disable_empty_topic");
    compose_state.topic(undefined);
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "channel", operand: rome_id.toString()}]);

    // Test with no topic, without realm mandatory topics
    override(realm, "realm_topics_policy", "allow_empty_topic");
    compose_state.topic(undefined);
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [
        {operator: "channel", operand: rome_id.toString()},
        {operator: "topic", operand: ""},
    ]);
});

run_test("narrow_to_compose_target direct messages", ({override, override_rewire}) => {
    const args = {called: false};
    override_rewire(message_view, "show", (terms, opts) => {
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
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "dm", operand: "alice@example.com"}]);

    // Test with valid persons
    emails = "alice@example.com,ray@example.com";
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "dm", operand: "alice@example.com,ray@example.com"}]);

    // Test with some invalid persons
    emails = "alice@example.com,random,ray@example.com";
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);

    // Test with all invalid persons
    emails = "alice,random,ray";
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);

    // Test with no persons
    emails = "";
    args.called = false;
    message_view.to_compose_target();
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
    const foo_stream_id = 43;
    const sub = {
        name: "Foo",
        stream_id: foo_stream_id,
    };
    stream_data.add_sub(sub);

    filter = new Filter([
        {operator: "stream", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
    ]);
    assert.equal(narrow_title.compute_narrow_title(filter), "#Foo > bar");

    filter = new Filter([{operator: "stream", operand: foo_stream_id.toString()}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "#Foo");

    filter = new Filter([{operator: "stream", operand: "Elephant"}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Unknown channel");

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

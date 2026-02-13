"use strict";

const assert = require("node:assert/strict");

const {make_user_group} = require("./lib/example_group.cjs");
const {make_realm} = require("./lib/example_realm.cjs");
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
const message_fetch = mock_esm("../src/message_fetch", {
    load_messages_around_anchor() {},
});
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
const realm = make_realm();
set_realm(realm);
initialize_user_settings({user_settings: {}});

set_global("document", "document-stub");
const message_lists = mock_esm("../src/message_lists", {
    update_current_message_list() {},
});
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
const settings_data = mock_esm("../src/settings_data");
mock_esm("../src/spectators", {
    login_to_access() {},
});

function empty_narrow_html(title, notice_html, search_data) {
    const opts = {
        title,
        notice_html,
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

const nobody = make_user_group({
    name: "role:nobody",
    id: 1,
    members: new Set(),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});
const everyone = make_user_group({
    name: "role:everyone",
    id: 2,
    members: new Set([5]),
    is_system_group: true,
    direct_subgroup_ids: new Set(),
});

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
            translated: Common words were excluded from your search: <br/>
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
            translated: Common words were excluded from your search: <br/>
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
    people.add_active_user(ray, "server_events");
    people.add_active_user(alice, "server_events");
    people.add_active_user(me, "server_events");
    people.initialize_current_user(me.user_id);

    let url = hash_util.pm_with_url(ray.user_id.toString());
    assert.equal(url, "#narrow/dm/22-Raymond");

    url = hash_util.direct_message_group_with_url("22,23");
    assert.equal(url, "#narrow/dm/22,23-group");

    url = hash_util.by_sender_url(ray.user_id);
    assert.equal(url, "#narrow/sender/22-Raymond");

    let user_ids = hash_util.decode_operand("dm", "22,23-group");
    assert.deepEqual(user_ids, [22, 23]);

    user_ids = hash_util.decode_operand("dm", "5,22,23-group");
    assert.deepEqual(user_ids, [22, 23]);

    user_ids = hash_util.decode_operand("dm", "5-group");
    assert.deepEqual(user_ids, [5]);
});

run_test("show_empty_narrow_message", ({mock_template, override, override_rewire}) => {
    settings_data.user_can_access_all_other_users = () => true;
    settings_data.user_has_permission_for_group_setting = () => true;
    override(realm, "stop_words", []);

    mock_template("empty_feed_notice.hbs", true, (_data, html) => html);

    // for empty combined feed
    let current_filter = new Filter([{operator: "in", operand: "home"}]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages in your combined feed.",
            'translated: Would you like to <a href="#narrow/channels/public">view messages in all public channels</a>?',
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
    stream_data.add_sub_for_tests({name: "ROME", stream_id: rome_id});
    current_filter = set_filter([["stream", rome_id.toString()]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
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
            'translated: This is not a <a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">publicly accessible</a> conversation.',
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
            'translated: This is not a <a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">publicly accessible</a> conversation.',
        ),
    );

    // for web-public stream for spectator
    const web_public_id = 1231;
    stream_data.add_sub_for_tests({
        name: "web-public-stream",
        stream_id: web_public_id,
        is_web_public: true,
    });
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
            'translated: Starring messages is a good way to keep track of important messages, such as tasks you need to go back to, or useful references. To star a message, hover over a message and click the <i class="zulip-icon zulip-icon-star" aria-hidden="true"></i>. <a target="_blank" rel="noopener noreferrer" href="/help/star-a-message">Learn more</a>',
        ),
    );

    current_filter = set_filter([["is", "mentioned"]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: This view will show messages where you are mentioned.",
            'translated: To call attention to a message, you can mention a user, a group, topic participants, or all subscribers to a channel. Type @ in the compose box, and choose who you\'d like to mention from the list of suggestions. <a target="_blank" rel="noopener noreferrer" href="/help/mention-a-user-or-group">Learn more</a>',
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
            'translated: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
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
    current_filter = set_filter([["dm", [-1]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    current_filter = set_filter([["dm", [9999, alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: One or more of these users do not exist!"),
    );

    current_filter = set_filter([["dm", [alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: Direct messages are disabled in this organization.",
            'translated: <a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">Learn more.</a>',
        ),
    );

    // direct messages with a bot are possible even though
    // the organization has disabled sending direct messages
    people.add_active_user(bot, "server_events");
    current_filter = set_filter([["dm", [bot.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with Example Bot yet.",
            'translated: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // group direct messages with bots are not possible when
    // sending direct messages is disabled
    current_filter = set_filter([["dm", [bot.user_id, alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: Direct messages are disabled in this organization.",
            'translated: <a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">Learn more.</a>',
        ),
    );

    // sending direct messages enabled
    override(realm, "realm_direct_message_permission_group", everyone.id);
    current_filter = set_filter([["dm", [alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with Alice Smith yet.",
            'translated: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // sending direct messages to deactivated user
    override(realm, "realm_direct_message_permission_group", everyone.id);
    people.deactivate(alice);
    current_filter = set_filter([["dm", [alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages with Alice Smith."),
    );
    people.add_active_user(alice);

    people.add_active_user(me);
    people.initialize_current_user(me.user_id);
    current_filter = set_filter([["dm", [me.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You haven't sent yourself any notes yet!",
            "translated: Use this space for personal notes, or to test out Zulip features.",
        ),
    );

    current_filter = set_filter([["dm", [me.user_id, alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You have no direct messages with these users yet.",
            'translated: Why not <a href="#" class="empty_feed_compose_private">start the conversation</a>?',
        ),
    );

    // group dm with a deactivated user
    people.deactivate(alice);
    current_filter = set_filter([["dm", [ray.user_id, alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages with these users."),
    );
    people.add_active_user(alice);

    // organization has disabled sending direct messages
    override(realm, "realm_direct_message_permission_group", nobody.id);

    // prioritize information about invalid user in narrow/search
    current_filter = set_filter([["dm-including", [-1]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    current_filter = set_filter([["dm-including", [9999, 88888]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: This user does not exist!"),
    );

    current_filter = set_filter([["dm-including", [alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: Direct messages are disabled in this organization.",
            'translated: <a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">Learn more.</a>',
        ),
    );

    // direct messages with a bot are possible even though
    // the organization has disabled sending direct messages
    current_filter = set_filter([["dm-including", [bot.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages including Example Bot yet."),
    );

    // sending direct messages enabled
    override(realm, "realm_direct_message_permission_group", everyone.id);
    override(realm, "realm_direct_message_permission_group", everyone.id);
    current_filter = set_filter([["dm-including", [alice.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You have no direct messages including Alice Smith yet."),
    );

    current_filter = set_filter([["dm-including", [me.user_id]]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You don't have any direct message conversations yet."),
    );

    current_filter = set_filter([["sender", ray.user_id]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html("translated: You haven't received any messages sent by Raymond yet."),
    );

    current_filter = set_filter([["sender", 9999]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: This user doesn't exist, or you are not allowed to view any of their messages.",
        ),
    );

    current_filter = set_filter([
        ["sender", alice.user_id],
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
            'translated: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
        ),
    );

    const my_stream_id = 103;
    const my_stream = {
        name: "my stream",
        stream_id: my_stream_id,
    };
    stream_data.add_sub_for_tests(my_stream);
    override_rewire(stream_data, "set_max_channel_width_css_variable", noop);
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
            'translated: To view a muted topic, click <b>show all topics</b> in the left sidebar, and select one from the list. <a target="_blank" rel="noopener noreferrer" href="/help/mute-a-topic">Learn more</a>',
        ),
    );
    // There are no muted topics in the channel.
    message_lists.current.empty = () => true;
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: There are no messages here.",
            'translated: Why not <a href="#" class="empty_feed_compose_stream">start the conversation</a>?',
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
        ["sender", me.user_id],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: None of your messages have emoji reactions yet.",
            'translated: Learn more about emoji reactions <a target="_blank" rel="noopener noreferrer" href="/help/emoji-reactions">here</a>.',
        ),
    );

    // The channel is private, and the user cannot subscribe (e.g., they
    // have access to channel metadata, but don't have content access).
    const private_sub = {
        stream_id: 101,
        name: "private",
        subscribed: false,
        invite_only: true,
    };
    stream_data.add_sub_for_tests(private_sub);
    settings_data.user_has_permission_for_group_setting = () => false;
    current_filter = set_filter([["stream", private_sub.stream_id.toString()]]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: You are not allowed to view messages in this private channel.",
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
    stream_data.add_sub_for_tests({name: "streamA", stream_id: streamA_id});
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
    stream_data.add_sub_for_tests({name: "streamA", stream_id: streamA_id});
    stream_data.add_sub_for_tests({name: "streamB", stream_id: streamB_id});

    let current_filter = set_filter([
        ["stream", streamA_id.toString()],
        ["stream", streamB_id.toString()],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated: <p>You are searching for messages that belong to more than one channel, which is not possible.</p>",
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
            "translated: <p>You are searching for messages that belong to more than one topic, which is not possible.</p>",
        ),
    );

    people.add_active_user(ray);
    people.add_active_user(alice);

    current_filter = set_filter([
        ["sender", alice.user_id],
        ["sender", ray.user_id],
    ]);
    narrow_banner.show_empty_narrow_message(current_filter);
    assert.equal(
        $(".empty_feed_notice_main").html(),
        empty_narrow_html(
            "translated: No search results.",
            "translated: <p>You are searching for messages that are sent by more than one person, which is not possible.</p>",
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
    stream_data.add_sub_for_tests({name: "ROME", stream_id: rome_id, topics_policy: "inherit"});
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

    let user_ids;
    override(compose_pm_pill, "get_user_ids", () => user_ids);

    compose_state.set_message_type("private");
    people.add_active_user(ray);
    people.add_active_user(alice);
    people.add_active_user(me);

    // Test with valid person
    user_ids = [alice.user_id];
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "dm", operand: [alice.user_id]}]);

    // Test with valid persons
    user_ids = [alice.user_id, ray.user_id];
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "dm", operand: [alice.user_id, ray.user_id]}]);

    // Test with some invalid persons
    user_ids = [alice.user_id, 9999, 8888];
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);

    // Test with all invalid persons
    user_ids = [9999, 8888];
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);

    // Test with no persons
    user_ids = [];
    args.called = false;
    message_view.to_compose_target();
    assert.equal(args.called, true);
    assert.deepEqual(args.terms, [{operator: "is", operand: "dm"}]);
});

run_test("fast_track_current_msg_list_to_anchor date", ({override}) => {
    const list = new MessageList({
        data: new MessageListData({
            excludes_muted_topics: false,
            filter: new Filter([]),
        }),
    });
    list.data.add_messages(
        [
            {id: 101, type: "stream", topic: "test", timestamp: 100, sender_id: me.user_id},
            {id: 102, type: "stream", topic: "test", timestamp: 200, sender_id: me.user_id},
            {id: 103, type: "stream", topic: "test", timestamp: 300, sender_id: me.user_id},
        ],
        true,
    );

    let selected;
    list.select_id = (id, opts) => {
        selected = {id, opts};
    };
    message_lists.current = list;

    const in_range = new Date(150 * 1000).toISOString();
    message_view.fast_track_current_msg_list_to_anchor("date", in_range);
    assert.deepEqual(selected, {
        id: 102,
        opts: {then_scroll: true, from_scroll: false},
    });

    list.data.fetch_status.finish_older_batch({
        found_oldest: true,
        history_limited: false,
        update_loading_indicator: false,
    });
    const before_range = new Date(50 * 1000).toISOString();
    message_view.fast_track_current_msg_list_to_anchor("date", before_range);
    assert.deepEqual(selected, {
        id: 101,
        opts: {then_scroll: true, from_scroll: false},
    });

    // If we have not found the oldest message, and the anchor timestamp is
    // at or before the first message, we should fetch from the server.
    override(message_fetch, "load_messages_around_anchor", (anchor, callback, msg_list_data) => {
        load_messages_calls += 1;
        load_messages_anchor = anchor;
        const new_message = {
            id: 100,
            type: "stream",
            topic: "test",
            timestamp: 75,
            sender_id: me.user_id,
        };
        list.data.add_messages([new_message], true);
        msg_list_data.add_messages(list.data.all_messages_after_mute_filtering(), true);
        msg_list_data.fetch_status.finish_older_batch({
            found_oldest: true,
            history_limited: false,
            update_loading_indicator: false,
        });
        callback();
    });
    list.data.fetch_status.finish_older_batch({
        found_oldest: false,
        history_limited: false,
        update_loading_indicator: false,
    });
    let load_messages_anchor;
    let load_messages_calls = 0;
    message_view.fast_track_current_msg_list_to_anchor("date", before_range);
    assert.equal(load_messages_calls, 1);
    assert.equal(load_messages_anchor, "date");
    assert.deepEqual(selected, {
        id: 100,
        opts: {then_scroll: true, from_scroll: false, force_rerender: true},
    });

    // Message 104 is not in the list so we need to fetch it from the API
    // using load_messages_around_anchor.
    load_messages_anchor = undefined;
    load_messages_calls = 0;
    override(message_fetch, "load_messages_around_anchor", (anchor, callback, msg_list_data) => {
        load_messages_calls += 1;
        load_messages_anchor = anchor;
        const new_message = {
            id: 104,
            type: "stream",
            topic: "test",
            timestamp: 400,
            sender_id: me.user_id,
        };
        list.data.add_messages([new_message], true);
        msg_list_data.add_messages(list.data.all_messages_after_mute_filtering(), true);
        callback();
    });
    assert.equal(list.data.get(104), undefined);
    const after_range = new Date(400 * 1000).toISOString();
    message_view.fast_track_current_msg_list_to_anchor("date", after_range);
    assert.equal(load_messages_calls, 1);
    assert.equal(load_messages_anchor, "date");
    assert.deepEqual(selected, {
        id: 104,
        opts: {then_scroll: true, from_scroll: false, force_rerender: true},
    });

    // If we have found the newest message, having anchor_date in
    // future should give you back the newest message.
    list.data.fetch_status.finish_newer_batch([], {
        found_newest: true,
        update_loading_indicator: false,
    });
    load_messages_calls = 0;
    const future_range = new Date(500 * 1000).toISOString();
    message_view.fast_track_current_msg_list_to_anchor("date", future_range);
    assert.deepEqual(selected, {
        id: 104,
        opts: {then_scroll: true, from_scroll: false},
    });
    assert.equal(load_messages_calls, 0);

    selected = undefined;
    blueslip.expect("error", "Missing required argument anchor_date");
    message_view.fast_track_current_msg_list_to_anchor("date");
    assert.equal(selected, undefined);
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

    filter = new Filter([{operator: "sender", operand: me.user_id}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Messages sent by you");

    // Stream narrows
    const foo_stream_id = 43;
    const sub = {
        name: "Foo",
        stream_id: foo_stream_id,
    };
    stream_data.add_sub_for_tests(sub);

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
    people.add_active_user(joe, "server_events");

    filter = new Filter([{operator: "dm", operand: [joe.user_id]}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "joe");

    filter = new Filter([{operator: "dm", operand: [9999, joe.user_id]}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Invalid users");

    filter = new Filter([{operator: "dm", operand: [9999]}]);
    assert.equal(narrow_title.compute_narrow_title(filter), "translated: Invalid user");
});

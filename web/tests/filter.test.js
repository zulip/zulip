"use strict";

const {strict: assert} = require("assert");

const {parseOneAddress} = require("email-addresses");

const {mock_esm, with_overrides, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {page_params, realm} = require("./lib/zpage_params");

const message_store = mock_esm("../src/message_store");

const resolved_topic = zrequire("../shared/src/resolved_topic");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const {Filter} = zrequire("../src/filter");

const stream_message = "stream";
const direct_message = "private";

const me = {
    email: "me@example.com",
    user_id: 30,
    full_name: "Me Myself",
};

const joe = {
    email: "joe@example.com",
    user_id: 31,
    full_name: "joe",
};

const steve = {
    email: "STEVE@foo.com",
    user_id: 32,
    full_name: "steve",
};

const alice = {
    email: "alice@example.com",
    user_id: 33,
    full_name: "alice",
    is_guest: true,
};

people.add_active_user(me);
people.add_active_user(joe);
people.add_active_user(steve);
people.add_active_user(alice);
people.initialize_current_user(me.user_id);

function assert_same_terms(result, terms) {
    // If negated flag is undefined, we explicitly
    // set it to false.
    terms = terms.map(({negated = false, operator, operand}) => ({negated, operator, operand}));
    assert.deepEqual(result, terms);
}

function get_predicate(raw_terms) {
    const terms = raw_terms.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    return new Filter(terms).predicate();
}

function make_sub(name, stream_id) {
    const sub = {
        name,
        stream_id,
    };
    stream_data.add_sub(sub);
}

function test(label, f) {
    run_test(label, (helpers) => {
        stream_data.clear_subscriptions();
        f(helpers);
    });
}

test("basics", () => {
    let terms = [
        {operator: "channel", operand: "foo"},
        {operator: "channel", operand: "exclude_me", negated: true},
        {operator: "topic", operand: "bar"},
    ];
    let filter = new Filter(terms);

    assert_same_terms(filter.terms(), terms);
    assert.deepEqual(filter.operands("channel"), ["foo"]);

    assert.ok(filter.has_operator("channel"));
    assert.ok(!filter.has_operator("search"));

    assert.ok(filter.has_operand("channel", "foo"));
    assert.ok(!filter.has_operand("channel", "exclude_me"));
    assert.ok(!filter.has_operand("channel", "nada"));

    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    assert.ok(filter.can_bucket_by("channel"));
    assert.ok(filter.can_bucket_by("channel", "topic"));

    // "stream" was renamed to "channel"
    terms = [{operator: "stream", operand: "foo"}];
    assert.ok(filter.has_operator("channel"));
    assert.deepEqual(filter.operands("channel"), ["foo"]);
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());

    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "channel", operand: "exclude_me", negated: true},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(terms);

    assert.deepEqual(filter.operands("channel"), ["foo"]);

    assert.ok(filter.has_operator("channel"));
    assert.ok(!filter.has_operator("search"));

    assert.ok(filter.has_operand("channel", "foo"));
    assert.ok(!filter.has_operand("channel", "exclude_me"));
    assert.ok(!filter.has_operand("channel", "nada"));

    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "pizza"},
    ];
    filter = new Filter(terms);

    assert.ok(filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.can_bucket_by("channel"));
    assert.ok(filter.can_bucket_by("channel", "topic"));
    assert.ok(!filter.is_conversation_view());

    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "near", operand: 17},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.can_bucket_by("channel"));
    assert.ok(filter.can_bucket_by("channel", "topic"));
    assert.ok(!filter.is_conversation_view());

    // If our only channel operator is negated, then for all intents and purposes,
    // we don't consider ourselves to have a channel operator, because we don't
    // want to have the channel in the tab bar or unsubscribe messaging, etc.
    terms = [{operator: "channel", operand: "exclude", negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("channel"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // Negated searches are just like positive searches for our purposes, since
    // the search logic happens on the backend and we need to have can_apply_locally()
    // be false, and we want "Search results" in the tab bar.
    terms = [{operator: "search", operand: "stop_word", negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.has_operator("search"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // Similar logic applies to negated "has" searches.
    terms = [{operator: "has", operand: "images", negated: true}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("has"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.can_apply_locally(true));
    assert.ok(!filter.includes_full_stream_history());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    terms = [{operator: "channels", operand: "public", negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("channels"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.has_negated_operand("channels", "public"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    terms = [{operator: "channels", operand: "public"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.has_operator("channels"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.has_negated_operand("channels", "public"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // "streams" was renamed to "channels"
    terms = [{operator: "streams", operand: "public"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("channels"));
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.includes_full_stream_history());

    terms = [{operator: "is", operand: "dm"}];
    filter = new Filter(terms);
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // "is:private" was renamed to "is:dm"
    terms = [{operator: "is", operand: "private"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operand("is", "dm"));
    assert.ok(!filter.has_operand("is", "private"));

    terms = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    terms = [{operator: "is", operand: "starred"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    terms = [{operator: "dm", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(filter.is_non_huddle_pm());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());

    terms = [{operator: "dm", operand: "joe@example.com,jack@example.com"}];
    filter = new Filter(terms);
    assert.ok(!filter.is_non_huddle_pm());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());

    // "pm-with" was renamed to "dm"
    terms = [{operator: "pm-with", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("dm"));
    assert.ok(!filter.has_operator("    pm-with"));

    terms = [{operator: "dm-including", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(!filter.is_non_huddle_pm());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // "group-pm-with" was replaced with "dm-including"
    terms = [{operator: "group-pm-with", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("dm-including"));
    assert.ok(!filter.has_operator("group-pm-with"));

    terms = [{operator: "is", operand: "resolved"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // Highly complex query to exercise
    // filter.supports_collapsing_recipients loop.
    terms = [
        {operator: "is", operand: "resolved", negated: true},
        {operator: "is", operand: "dm", negated: true},
        {operator: "channel", operand: "channel_name", negated: true},
        {operator: "channels", operand: "web-public", negated: true},
        {operator: "channels", operand: "public"},
        {operator: "topic", operand: "patience", negated: true},
        {operator: "in", operand: "all"},
    ];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    // This next check verifies what is probably a bug; see the
    // comment in the can_apply_locally implementation.
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());

    // "stream" was renamed to "channel"
    terms = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
});

function assert_not_mark_read_with_has_operands(additional_terms_to_test) {
    additional_terms_to_test = additional_terms_to_test || [];
    let has_link_term = [{operator: "has", operand: "link"}];
    let filter = new Filter([...additional_terms_to_test, ...has_link_term]);
    assert.ok(!filter.can_mark_messages_read());

    has_link_term = [{operator: "has", operand: "link", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...has_link_term]);
    assert.ok(!filter.can_mark_messages_read());

    has_link_term = [{operator: "has", operand: "image"}];
    filter = new Filter([...additional_terms_to_test, ...has_link_term]);
    assert.ok(!filter.can_mark_messages_read());

    has_link_term = [{operator: "has", operand: "image", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...has_link_term]);
    assert.ok(!filter.can_mark_messages_read());

    has_link_term = [{operator: "has", operand: "attachment", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...has_link_term]);
    assert.ok(!filter.can_mark_messages_read());

    has_link_term = [{operator: "has", operand: "attachment"}];
    filter = new Filter([...additional_terms_to_test, ...has_link_term]);
    assert.ok(!filter.can_mark_messages_read());
}
function assert_not_mark_read_with_is_operands(additional_terms_to_test) {
    additional_terms_to_test = additional_terms_to_test || [];
    let is_operator = [{operator: "is", operand: "starred"}];
    let filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "starred", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "mentioned"}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "mentioned", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "alerted"}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "alerted", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "unread"}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "unread", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "resolved"}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    if (additional_terms_to_test.length === 0) {
        assert.ok(filter.can_mark_messages_read());
    } else {
        assert.ok(!filter.can_mark_messages_read());
    }

    is_operator = [{operator: "is", operand: "resolved", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());
}

function assert_not_mark_read_when_searching(additional_terms_to_test) {
    additional_terms_to_test = additional_terms_to_test || [];
    let search_op = [{operator: "search", operand: "keyword"}];
    let filter = new Filter([...additional_terms_to_test, ...search_op]);
    assert.ok(!filter.can_mark_messages_read());

    search_op = [{operator: "search", operand: "keyword", negated: true}];
    filter = new Filter([...additional_terms_to_test, ...search_op]);
    assert.ok(!filter.can_mark_messages_read());
}

test("can_mark_messages_read", () => {
    assert_not_mark_read_with_has_operands();
    assert_not_mark_read_with_is_operands();
    assert_not_mark_read_when_searching();

    const channel_term = [{operator: "channel", operand: "foo"}];
    let filter = new Filter(channel_term);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(channel_term);
    assert_not_mark_read_with_is_operands(channel_term);
    assert_not_mark_read_when_searching(channel_term);

    const channel_negated_operator = [{operator: "channel", operand: "foo", negated: true}];
    filter = new Filter(channel_negated_operator);
    assert.ok(!filter.can_mark_messages_read());

    const channel_topic_terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(channel_topic_terms);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(channel_topic_terms);
    assert_not_mark_read_with_is_operands(channel_topic_terms);
    assert_not_mark_read_when_searching(channel_topic_terms);

    const channel_negated_topic_terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar", negated: true},
    ];
    filter = new Filter(channel_negated_topic_terms);
    assert.ok(!filter.can_mark_messages_read());

    const dm = [{operator: "dm", operand: "joe@example.com,"}];

    const dm_negated = [{operator: "dm", operand: "joe@example.com,", negated: true}];

    const dm_group = [{operator: "dm", operand: "joe@example.com,STEVE@foo.com"}];
    filter = new Filter(dm);
    assert.ok(filter.can_mark_messages_read());
    filter = new Filter(dm_negated);
    assert.ok(!filter.can_mark_messages_read());
    filter = new Filter(dm_group);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(dm_group);
    assert_not_mark_read_with_is_operands(dm);
    assert_not_mark_read_with_has_operands(dm_group);
    assert_not_mark_read_with_has_operands(dm);
    assert_not_mark_read_when_searching(dm_group);
    assert_not_mark_read_when_searching(dm);

    const is_dm = [{operator: "is", operand: "dm"}];
    filter = new Filter(is_dm);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(is_dm);
    assert_not_mark_read_with_has_operands(is_dm);
    assert_not_mark_read_when_searching(is_dm);

    const in_all = [{operator: "in", operand: "all"}];
    filter = new Filter(in_all);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(in_all);
    assert_not_mark_read_with_has_operands(in_all);
    assert_not_mark_read_when_searching(in_all);

    const in_home = [{operator: "in", operand: "home"}];
    const in_home_negated = [{operator: "in", operand: "home", negated: true}];
    filter = new Filter(in_home);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(in_home);
    assert_not_mark_read_with_has_operands(in_home);
    assert_not_mark_read_when_searching(in_home);
    filter = new Filter(in_home_negated);
    assert.ok(!filter.can_mark_messages_read());

    // Do not mark messages as read when in an unsupported 'in:*' filter.
    const in_random = [{operator: "in", operand: "xxxxxxxxx"}];
    const in_random_negated = [{operator: "in", operand: "xxxxxxxxx", negated: true}];
    filter = new Filter(in_random);
    assert.ok(!filter.can_mark_messages_read());
    filter = new Filter(in_random_negated);
    assert.ok(!filter.can_mark_messages_read());

    // test caching of term types
    // init and stub
    filter = new Filter(dm);
    filter.stub = filter.calc_can_mark_messages_read;
    filter.calc_can_mark_messages_read = function () {
        this.calc_can_mark_messages_read_called = true;
        return this.stub();
    };

    // uncached trial
    filter.calc_can_mark_messages_read_called = false;
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.calc_can_mark_messages_read_called);

    // cached trial
    filter.calc_can_mark_messages_read_called = false;
    assert.ok(filter.can_mark_messages_read());
    assert.ok(!filter.calc_can_mark_messages_read_called);
});

test("show_first_unread", () => {
    let terms = [{operator: "is", operand: "any"}];
    let filter = new Filter(terms);
    assert.ok(filter.allow_use_first_unread_when_narrowing());

    terms = [{operator: "search", operand: "query to search"}];
    filter = new Filter(terms);
    assert.ok(!filter.allow_use_first_unread_when_narrowing());

    filter = new Filter([]);
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.allow_use_first_unread_when_narrowing());

    // Side case
    terms = [{operator: "is", operand: "any"}];
    filter = new Filter(terms);
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
});

test("filter_with_new_params_topic", () => {
    const terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(terms);

    assert.ok(filter.has_topic("foo", "old topic"));
    assert.ok(!filter.has_topic("wrong", "old topic"));
    assert.ok(!filter.has_topic("foo", "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "topic",
        operand: "new topic",
    });

    assert.deepEqual(new_filter.operands("channel"), ["foo"]);
    assert.deepEqual(new_filter.operands("topic"), ["new topic"]);
});

test("filter_with_new_params_channel", () => {
    const terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(terms);

    assert.ok(filter.has_topic("foo", "old topic"));
    assert.ok(!filter.has_topic("wrong", "old topic"));
    assert.ok(!filter.has_topic("foo", "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "channel",
        operand: "new channel",
    });

    assert.deepEqual(new_filter.operands("channel"), ["new channel"]);
    assert.deepEqual(new_filter.operands("topic"), ["old topic"]);
});

test("new_style_terms", () => {
    const term = {
        operator: "channel",
        operand: "foo",
    };
    const terms = [term];
    const filter = new Filter(terms);

    assert.deepEqual(filter.operands("channel"), ["foo"]);
    assert.ok(filter.can_bucket_by("channel"));
});

test("public_terms", ({override}) => {
    stream_data.clear_subscriptions();
    let terms = [
        {operator: "channel", operand: "some_channel"},
        {operator: "in", operand: "all"},
        {operator: "topic", operand: "bar"},
    ];
    let filter = new Filter(terms);
    const expected_terms = [
        {operator: "channel", operand: "some_channel"},
        {operator: "in", operand: "all"},
        {operator: "topic", operand: "bar"},
    ];
    override(page_params, "narrow_stream", undefined);
    assert_same_terms(filter.public_terms(), expected_terms);
    assert.ok(filter.can_bucket_by("channel"));

    terms = [{operator: "channel", operand: "default"}];
    filter = new Filter(terms);
    override(page_params, "narrow_stream", "default");
    assert_same_terms(filter.public_terms(), []);
});

test("redundancies", () => {
    let terms;
    let filter;

    terms = [
        {operator: "dm", operand: "joe@example.com,"},
        {operator: "is", operand: "dm"},
    ];
    filter = new Filter(terms);
    assert.ok(filter.can_bucket_by("dm"));

    terms = [
        {operator: "dm", operand: "joe@example.com,", negated: true},
        {operator: "is", operand: "dm"},
    ];
    filter = new Filter(terms);
    assert.ok(filter.can_bucket_by("is-dm", "not-dm"));
});

test("canonicalization", () => {
    assert.equal(Filter.canonicalize_operator("Is"), "is");
    assert.equal(Filter.canonicalize_operator("Stream"), "channel");
    assert.equal(Filter.canonicalize_operator("Subject"), "topic");
    assert.equal(Filter.canonicalize_operator("FROM"), "sender");

    let term;
    term = Filter.canonicalize_term({operator: "Stream", operand: "Denmark"});
    assert.equal(term.operator, "channel");
    assert.equal(term.operand, "Denmark");

    term = Filter.canonicalize_term({operator: "Channel", operand: "Denmark"});
    assert.equal(term.operator, "channel");
    assert.equal(term.operand, "Denmark");

    term = Filter.canonicalize_term({operator: "sender", operand: "me"});
    assert.equal(term.operator, "sender");
    assert.equal(term.operand, "me@example.com");

    // "pm-with" was renamed to "dm"
    term = Filter.canonicalize_term({operator: "pm-with", operand: "me"});
    assert.equal(term.operator, "dm");
    assert.equal(term.operand, "me@example.com");

    // "group-pm-with" was replaced with "dm-including"
    term = Filter.canonicalize_term({operator: "group-pm-with", operand: "joe@example.com"});
    assert.equal(term.operator, "dm-including");
    assert.equal(term.operand, "joe@example.com");

    term = Filter.canonicalize_term({operator: "search", operand: "foo"});
    assert.equal(term.operator, "search");
    assert.equal(term.operand, "foo");

    term = Filter.canonicalize_term({operator: "search", operand: "fOO"});
    assert.equal(term.operator, "search");
    assert.equal(term.operand, "foo");

    term = Filter.canonicalize_term({operator: "search", operand: 123});
    assert.equal(term.operator, "search");
    assert.equal(term.operand, "123");

    term = Filter.canonicalize_term({operator: "search", operand: "abc “xyz”"});
    assert.equal(term.operator, "search");
    assert.equal(term.operand, 'abc "xyz"');

    term = Filter.canonicalize_term({operator: "has", operand: "attachments"});
    assert.equal(term.operator, "has");
    assert.equal(term.operand, "attachment");

    term = Filter.canonicalize_term({operator: "has", operand: "images"});
    assert.equal(term.operator, "has");
    assert.equal(term.operand, "image");

    term = Filter.canonicalize_term({operator: "has", operand: "links"});
    assert.equal(term.operator, "has");
    assert.equal(term.operand, "link");
});

test("predicate_basics", () => {
    // Predicates are functions that accept a message object with the message
    // attributes (not content), and return true if the message belongs in a
    // given narrow. If the narrow parameters include a search, the predicate
    // passes through all messages.
    //
    // To keep these tests simple, we only pass objects with a few relevant attributes
    // rather than full-fledged message objects.

    const stream_id = 42;
    make_sub("Foo", stream_id);
    let predicate = get_predicate([
        ["channel", "Foo"],
        ["topic", "Bar"],
    ]);

    assert.ok(predicate({type: stream_message, stream_id, topic: "bar"}));
    assert.ok(!predicate({type: stream_message, stream_id, topic: "whatever"}));
    // 9999999 doesn't exist, testing no match
    assert.ok(!predicate({type: stream_message, stream_id: 9999999}));
    assert.ok(!predicate({type: direct_message}));

    // For old channels that we are no longer subscribed to, we may not have
    // a subscription, but these should still match by channel name.
    const old_sub = {
        name: "old-subscription",
        stream_id: 5,
        subscribed: false,
    };
    stream_data.add_sub(old_sub);
    predicate = get_predicate([
        ["channel", "old-subscription"],
        ["topic", "Bar"],
    ]);
    assert.ok(predicate({type: stream_message, stream_id: 5, topic: "bar"}));
    // 99999 doesn't exist, testing no match
    assert.ok(!predicate({type: stream_message, stream_id: 99999, topic: "whatever"}));

    predicate = get_predicate([["search", "emoji"]]);
    assert.ok(predicate({}));

    predicate = get_predicate([["topic", "Bar"]]);
    assert.ok(!predicate({type: direct_message}));

    predicate = get_predicate([["is", "dm"]]);
    assert.ok(predicate({type: direct_message}));
    assert.ok(!predicate({type: stream_message}));

    predicate = get_predicate([["channels", "public"]]);
    assert.ok(predicate({}));

    predicate = get_predicate([["is", "starred"]]);
    assert.ok(predicate({starred: true}));
    assert.ok(!predicate({starred: false}));

    predicate = get_predicate([["is", "unread"]]);
    assert.ok(predicate({unread: true}));
    assert.ok(!predicate({unread: false}));

    predicate = get_predicate([["is", "alerted"]]);
    assert.ok(predicate({alerted: true}));
    assert.ok(!predicate({alerted: false}));
    assert.ok(!predicate({}));

    predicate = get_predicate([["is", "mentioned"]]);
    assert.ok(predicate({mentioned: true}));
    assert.ok(!predicate({mentioned: false}));

    predicate = get_predicate([["in", "all"]]);
    assert.ok(predicate({}));

    predicate = get_predicate([["is", "resolved"]]);
    const resolved_topic_name = resolved_topic.resolve_name("foo");
    assert.ok(predicate({type: stream_message, topic: resolved_topic_name}));
    assert.ok(!predicate({topic: resolved_topic_name}));
    assert.ok(!predicate({type: stream_message, topic: "foo"}));

    const unknown_stream_id = 999;
    predicate = get_predicate([["in", "home"]]);
    assert.ok(!predicate({stream_id: unknown_stream_id, stream: "unknown"}));
    assert.ok(predicate({type: direct_message}));

    make_sub("kiosk", 1234);
    with_overrides(({override}) => {
        override(page_params, "narrow_stream", "kiosk");
        assert.ok(predicate({stream_id: 1234}));
    });

    predicate = get_predicate([["near", 5]]);
    assert.ok(predicate({}));

    predicate = get_predicate([["id", 5]]);
    assert.ok(predicate({id: 5}));
    assert.ok(!predicate({id: 6}));

    predicate = get_predicate([
        ["id", 5],
        ["topic", "lunch"],
    ]);
    assert.ok(predicate({type: stream_message, id: 5, topic: "lunch"}));
    assert.ok(!predicate({type: stream_message, id: 5, topic: "dinner"}));

    predicate = get_predicate([["sender", "Joe@example.com"]]);
    assert.ok(predicate({sender_id: joe.user_id}));
    assert.ok(!predicate({sender_email: steve.user_id}));

    predicate = get_predicate([["dm", "Joe@example.com"]]);
    assert.ok(
        predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}],
        }),
    );
    assert.ok(
        !predicate({
            type: direct_message,
            display_recipient: [{id: steve.user_id}],
        }),
    );
    assert.ok(
        !predicate({
            type: direct_message,
            display_recipient: [{id: 999999}],
        }),
    );
    assert.ok(!predicate({type: stream_message}));

    predicate = get_predicate([["dm", "Joe@example.com,steve@foo.com"]]);
    assert.ok(
        predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );

    // Make sure your own email is ignored
    predicate = get_predicate([["dm", "Joe@example.com,steve@foo.com,me@example.com"]]);
    assert.ok(
        predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );

    predicate = get_predicate([["dm", "nobody@example.com"]]);
    assert.ok(
        !predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}],
        }),
    );

    predicate = get_predicate([["dm-including", "nobody@example.com"]]);
    assert.ok(
        !predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}, {id: me.user_id}],
        }),
    );

    predicate = get_predicate([["dm-including", "Joe@example.com"]]);
    assert.ok(
        predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}, {id: me.user_id}],
        }),
    );
    assert.ok(
        predicate({
            type: direct_message,
            display_recipient: [{id: joe.user_id}, {id: me.user_id}],
        }),
    );
    assert.ok(
        !predicate({
            type: direct_message,
            display_recipient: [{id: steve.user_id}, {id: me.user_id}],
        }),
    );
    assert.ok(!predicate({type: stream_message}));

    const img_msg = {
        content:
            '<p><a href="/user_uploads/randompath/test.jpeg">test.jpeg</a></p><div class="message_inline_image"><a href="/user_uploads/randompath/test.jpeg" title="test.jpeg"><img src="/user_uploads/randompath/test.jpeg"></a></div>',
    };

    const link_msg = {
        content: '<p><a href="http://chat.zulip.org">chat.zulip.org</a></p>',
    };

    const non_img_attachment_msg = {
        content: '<p><a href="/user_uploads/randompath/attachment.ext">attachment.ext</a></p>',
    };

    const no_has_filter_matching_msg = {
        content: "<p>Testing</p>",
    };

    predicate = get_predicate([["has", "non_valid_operand"]]);
    assert.ok(!predicate(img_msg));
    assert.ok(!predicate(non_img_attachment_msg));
    assert.ok(!predicate(link_msg));
    assert.ok(!predicate(no_has_filter_matching_msg));

    // HTML content of message is used to determine if image have link, image or attachment.
    // We are using jquery to parse the html and find existence of relevant tags/elements.
    // In tests we need to stub the calls to jquery so using zjquery's .set_find_results method.
    function set_find_results_for_msg_content(msg, jquery_selector, results) {
        $(`<div>${msg.content}</div>`).set_find_results(jquery_selector, results);
    }

    const has_link = get_predicate([["has", "link"]]);
    set_find_results_for_msg_content(img_msg, "a", ["stub"]);
    assert.ok(has_link(img_msg));
    set_find_results_for_msg_content(non_img_attachment_msg, "a", ["stub"]);
    assert.ok(has_link(non_img_attachment_msg));
    set_find_results_for_msg_content(link_msg, "a", ["stub"]);
    assert.ok(has_link(link_msg));
    set_find_results_for_msg_content(no_has_filter_matching_msg, "a", false);
    assert.ok(!has_link(no_has_filter_matching_msg));

    const has_attachment = get_predicate([["has", "attachment"]]);
    set_find_results_for_msg_content(img_msg, "a[href^='/user_uploads']", ["stub"]);
    assert.ok(has_attachment(img_msg));
    set_find_results_for_msg_content(non_img_attachment_msg, "a[href^='/user_uploads']", ["stub"]);
    assert.ok(has_attachment(non_img_attachment_msg));
    set_find_results_for_msg_content(link_msg, "a[href^='/user_uploads']", false);
    assert.ok(!has_attachment(link_msg));
    set_find_results_for_msg_content(no_has_filter_matching_msg, "a[href^='/user_uploads']", false);
    assert.ok(!has_attachment(no_has_filter_matching_msg));

    const has_image = get_predicate([["has", "image"]]);
    set_find_results_for_msg_content(img_msg, ".message_inline_image", ["stub"]);
    assert.ok(has_image(img_msg));
    set_find_results_for_msg_content(non_img_attachment_msg, ".message_inline_image", false);
    assert.ok(!has_image(non_img_attachment_msg));
    set_find_results_for_msg_content(link_msg, ".message_inline_image", false);
    assert.ok(!has_image(link_msg));
    set_find_results_for_msg_content(no_has_filter_matching_msg, ".message_inline_image", false);
    assert.ok(!has_image(no_has_filter_matching_msg));
});

test("negated_predicates", () => {
    let predicate;
    let narrow;

    const social_stream_id = 555;
    make_sub("social", social_stream_id);

    narrow = [{operator: "channel", operand: "social", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert.ok(predicate({type: stream_message, stream_id: 999999}));
    assert.ok(!predicate({type: stream_message, stream_id: social_stream_id}));

    narrow = [{operator: "channels", operand: "public", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert.ok(predicate({}));
});

function test_mit_exceptions() {
    const foo_stream_id = 555;
    make_sub("Foo", foo_stream_id);
    let predicate = get_predicate([
        ["channel", "Foo"],
        ["topic", "personal"],
    ]);
    assert.ok(predicate({type: stream_message, stream_id: foo_stream_id, topic: "personal"}));
    assert.ok(predicate({type: stream_message, stream_id: foo_stream_id, topic: ""}));
    // 9999 doesn't correspond to any channel
    assert.ok(!predicate({type: stream_message, stream_id: 9999}));
    assert.ok(!predicate({type: stream_message, stream_id: foo_stream_id, topic: "whatever"}));
    assert.ok(!predicate({type: direct_message}));

    predicate = get_predicate([
        ["channel", "Foo"],
        ["topic", "bar"],
    ]);
    assert.ok(predicate({type: stream_message, stream_id: foo_stream_id, topic: "bar.d"}));

    // Try to get the MIT regex to explode for an empty channel.
    let terms = [
        {operator: "channel", operand: ""},
        {operator: "topic", operand: "bar"},
    ];
    predicate = new Filter(terms).predicate();
    assert.ok(!predicate({type: stream_message, stream_id: foo_stream_id, topic: "bar"}));

    // Try to get the MIT regex to explode for an empty topic.
    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: ""},
    ];
    predicate = new Filter(terms).predicate();
    assert.ok(!predicate({type: stream_message, stream_id: foo_stream_id, topic: "bar"}));
}

test("mit_exceptions", ({override}) => {
    override(realm, "realm_is_zephyr_mirror_realm", true);
    test_mit_exceptions();
});

test("predicate_edge_cases", () => {
    let predicate;
    // The code supports undefined as an operator to Filter, which results
    // in a predicate that accepts any message.
    predicate = new Filter([]).predicate();
    assert.ok(predicate({}));

    // Upstream code should prevent Filter.predicate from being called with
    // invalid operator/operand combinations, but right now we just silently
    // return a function that accepts all messages.
    predicate = get_predicate([["in", "bogus"]]);
    assert.ok(!predicate({}));

    predicate = get_predicate([["bogus", 33]]);
    assert.ok(predicate({}));

    predicate = get_predicate([["is", "bogus"]]);
    assert.ok(!predicate({}));

    // Exercise caching feature.
    const stream_id = 101;
    make_sub("Off topic", stream_id);
    const terms = [
        {operator: "channel", operand: "Off topic"},
        {operator: "topic", operand: "Mars"},
    ];
    const filter = new Filter(terms);
    filter.predicate();
    predicate = filter.predicate(); // get cached version
    assert.ok(predicate({type: stream_message, stream_id, topic: "Mars"}));
});

test("parse", () => {
    let string;
    let terms;

    function _test() {
        const result = Filter.parse(string);
        assert_same_terms(result, terms);
    }

    string = "channel:Foo topic:Bar yo";
    terms = [
        {operator: "channel", operand: "Foo"},
        {operator: "topic", operand: "Bar"},
        {operator: "search", operand: "yo"},
    ];
    _test();

    // "stream" was renamed to "channel"
    string = "stream:Foo topic:Bar yo";
    terms = [
        {operator: "stream", operand: "Foo"},
        {operator: "topic", operand: "Bar"},
        {operator: "search", operand: "yo"},
    ];
    _test();

    string = "dm:leo+test@zulip.com";
    terms = [{operator: "dm", operand: "leo+test@zulip.com"}];
    _test();

    string = "sender:leo+test@zulip.com";
    terms = [{operator: "sender", operand: "leo+test@zulip.com"}];
    _test();

    string = "channel:With+Space";
    terms = [{operator: "channel", operand: "With Space"}];
    _test();

    string = 'channel:"with quoted space" topic:and separate';
    terms = [
        {operator: "channel", operand: "with quoted space"},
        {operator: "topic", operand: "and"},
        {operator: "search", operand: "separate"},
    ];
    _test();

    string = 'channel:"unclosed quote';
    terms = [{operator: "channel", operand: "unclosed quote"}];
    _test();

    string = 'channel:""';
    terms = [{operator: "channel", operand: ""}];
    _test();

    string = "https://www.google.com";
    terms = [{operator: "search", operand: "https://www.google.com"}];
    _test();

    string = "channel:foo -channel:exclude";
    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "channel", operand: "exclude", negated: true},
    ];
    _test();

    string = "text channel:foo more text";
    terms = [
        {operator: "search", operand: "text"},
        {operator: "channel", operand: "foo"},
        {operator: "search", operand: "more text"},
    ];
    _test();

    string = "text channels:public more text";
    terms = [
        {operator: "search", operand: "text"},
        {operator: "channels", operand: "public"},
        {operator: "search", operand: "more text"},
    ];
    _test();

    string = "channels:public";
    terms = [{operator: "channels", operand: "public"}];
    _test();

    string = "-channels:public";
    terms = [{operator: "channels", operand: "public", negated: true}];
    _test();

    // "streams" was renamed to "channels"
    string = "streams:public";
    terms = [{operator: "streams", operand: "public"}];
    _test();

    string = "channel:foo :emoji: are cool";
    terms = [
        {operator: "channel", operand: "foo"},
        {operator: "search", operand: ":emoji: are cool"},
    ];
    _test();

    string = ":channel: channel:foo :emoji: are cool";
    terms = [
        {operator: "search", operand: ":channel:"},
        {operator: "channel", operand: "foo"},
        {operator: "search", operand: ":emoji: are cool"},
    ];
    _test();

    string = ":channel: channel:foo -:emoji: are cool";
    terms = [
        {operator: "search", operand: ":channel:"},
        {operator: "channel", operand: "foo"},
        {operator: "search", operand: "-:emoji: are cool"},
    ];
    _test();

    string = "";
    terms = [];
    _test();

    string = 'channel: separated topic: "with space"';
    terms = [
        {operator: "channel", operand: "separated"},
        {operator: "topic", operand: "with space"},
    ];
    _test();
});

test("unparse", () => {
    let string;
    let terms;

    terms = [
        {operator: "channel", operand: "Foo"},
        {operator: "topic", operand: "Bar", negated: true},
        {operator: "search", operand: "yo"},
    ];
    string = "channel:Foo -topic:Bar yo";
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [
        {operator: "channels", operand: "public"},
        {operator: "search", operand: "text"},
    ];

    string = "channels:public text";
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [{operator: "channels", operand: "public"}];
    string = "channels:public";
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [{operator: "channels", operand: "public", negated: true}];
    string = "-channels:public";
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [{operator: "id", operand: 50}];
    string = "id:50";
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [{operator: "near", operand: 150}];
    string = "near:150";
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [{operator: "", operand: ""}];
    string = "";
    assert.deepEqual(Filter.unparse(terms), string);

    // canonical version of the operator is
    // used in the unparsed search string
    terms = [
        {operator: "stream", operand: "Foo"},
        {operator: "subject", operand: "Bar"},
    ];
    string = "channel:Foo topic:Bar";
    assert.deepEqual(Filter.unparse(terms), string);
});

test("describe", ({mock_template}) => {
    let narrow;
    let string;
    mock_template("search_description.hbs", true, (_data, html) => html);

    narrow = [{operator: "channels", operand: "public"}];
    string = "channels public";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "channels", operand: "public", negated: true}];
    string = "exclude channels public";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "channel", operand: "devel"},
        {operator: "is", operand: "starred"},
    ];
    string = "channel devel, starred messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "channel", operand: "river"},
        {operator: "is", operand: "unread"},
    ];
    string = "channel river, unread messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "channel", operand: "devel"},
        {operator: "topic", operand: "JS"},
    ];
    string = "channel devel > JS";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "is", operand: "dm"},
        {operator: "search", operand: "lunch"},
    ];
    string = "direct messages, search for lunch";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "id", operand: 99}];
    string = "message ID 99";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "in", operand: "home"}];
    string = "messages in home";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "is", operand: "mentioned"}];
    string = "@-mentions";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "is", operand: "alerted"}];
    string = "alerted messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "is", operand: "resolved"}];
    string = "topics marked as resolved";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "is", operand: "something_we_do_not_support"}];
    string = "invalid something_we_do_not_support operand for is operator";
    assert.equal(Filter.search_description_as_html(narrow), string);

    // this should be unreachable, but just in case
    narrow = [{operator: "bogus", operand: "foo"}];
    string = "unknown operator";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "channel", operand: "devel"},
        {operator: "topic", operand: "JS", negated: true},
    ];
    string = "channel devel, exclude topic JS";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "is", operand: "dm"},
        {operator: "search", operand: "lunch", negated: true},
    ];
    string = "direct messages, exclude lunch";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "channel", operand: "devel"},
        {operator: "is", operand: "starred", negated: true},
    ];
    string = "channel devel, exclude starred messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "channel", operand: "devel"},
        {operator: "has", operand: "image", negated: true},
    ];
    string = "channel devel, exclude messages with one or more image";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "has", operand: "abc", negated: true},
        {operator: "channel", operand: "devel"},
    ];
    string = "invalid abc operand for has operator, channel devel";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "has", operand: "image", negated: true},
        {operator: "channel", operand: "devel"},
    ];
    string = "exclude messages with one or more image, channel devel";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [];
    string = "combined feed";
    assert.equal(Filter.search_description_as_html(narrow), string);

    // canonical version of the operator is used in description
    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "subject", operand: "JS", negated: true},
    ];
    string = "channel devel, exclude topic JS";
    assert.equal(Filter.search_description_as_html(narrow), string);
});

test("can_bucket_by", () => {
    let terms = [{operator: "channel", operand: "My channel"}];
    let filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), true);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [
        // try a non-orthodox ordering
        {operator: "topic", operand: "My topic"},
        {operator: "channel", operand: "My channel"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), true);
    assert.equal(filter.can_bucket_by("channel", "topic"), true);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [
        {operator: "channel", operand: "My channel", negated: true},
        {operator: "topic", operand: "My topic"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), false);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [{operator: "dm", operand: "foo@example.com", negated: true}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), false);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [{operator: "dm", operand: "foo@example.com,bar@example.com"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), false);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), true);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-dm"), false);

    terms = [{operator: "is", operand: "dm"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-dm"), true);

    terms = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), true);
    assert.equal(filter.can_bucket_by("is-dm"), false);

    terms = [
        {operator: "is", operand: "mentioned"},
        {operator: "is", operand: "starred"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), true);
    assert.equal(filter.can_bucket_by("is-dm"), false);

    // The call below returns false for somewhat arbitrary
    // reasons -- we say is-dm has precedence over
    // is-starred.
    assert.equal(filter.can_bucket_by("is-starred"), false);

    terms = [{operator: "is", operand: "mentioned", negated: true}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-dm"), false);

    terms = [{operator: "is", operand: "resolved"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("channel"), false);
    assert.equal(filter.can_bucket_by("dm"), false);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-dm"), false);
});

test("term_type", () => {
    function assert_term_type(term, expected_term_type) {
        assert.equal(Filter.term_type(term), expected_term_type);
    }

    function term(operator, operand, negated) {
        return {
            operator,
            operand,
            negated,
        };
    }

    assert_term_type(term("channels", "public"), "channels-public");
    assert_term_type(term("channel", "whatever"), "channel");
    assert_term_type(term("dm", "whomever"), "dm");
    assert_term_type(term("dm", "whomever", true), "not-dm");
    assert_term_type(term("is", "dm"), "is-dm");
    assert_term_type(term("is", "private"), "is-private");
    assert_term_type(term("has", "link"), "has-link");
    assert_term_type(term("has", "attachment", true), "not-has-attachment");

    function assert_term_sort(in_terms, expected) {
        const sorted_terms = Filter.sorted_term_types(in_terms);
        assert.deepEqual(sorted_terms, expected);
    }

    assert_term_sort(["topic", "channel", "sender"], ["channel", "topic", "sender"]);

    assert_term_sort(
        ["has-link", "near", "is-unread", "dm"],
        ["dm", "near", "is-unread", "has-link"],
    );

    assert_term_sort(["bogus", "channel", "topic"], ["channel", "topic", "bogus"]);
    assert_term_sort(["channel", "topic", "channel"], ["channel", "channel", "topic"]);

    assert_term_sort(["search", "channels-public"], ["channels-public", "search"]);

    const terms = [
        {operator: "topic", operand: "lunch"},
        {operator: "sender", operand: "steve@foo.com"},
        {operator: "channel", operand: "Verona"},
    ];
    let filter = new Filter(terms);
    const term_types = filter.sorted_term_types();

    assert.deepEqual(term_types, ["channel", "topic", "sender"]);

    // test caching of term types
    // init and stub
    filter = new Filter(terms);
    filter.stub = filter._build_sorted_term_types;
    filter._build_sorted_term_types = function () {
        this._build_sorted_term_types_called = true;
        return this.stub();
    };

    // uncached trial
    filter._build_sorted_term_types_called = false;
    const built_terms = filter.sorted_term_types();
    assert.deepEqual(built_terms, ["channel", "topic", "sender"]);
    assert.ok(filter._build_sorted_term_types_called);

    // cached trial
    filter._build_sorted_term_types_called = false;
    const cached_terms = filter.sorted_term_types();
    assert.deepEqual(cached_terms, ["channel", "topic", "sender"]);
    assert.ok(!filter._build_sorted_term_types_called);
});

test("first_valid_id_from", ({override}) => {
    const terms = [{operator: "is", operand: "alerted"}];

    const filter = new Filter(terms);

    const messages = {
        5: {id: 5, alerted: true},
        10: {id: 10},
        20: {id: 20, alerted: true},
        30: {id: 30, type: stream_message},
        40: {id: 40, alerted: false},
    };

    const msg_ids = [10, 20, 30, 40];

    override(message_store, "get", (msg_id) => messages[msg_id]);

    assert.equal(filter.first_valid_id_from([999]), undefined);

    assert.equal(filter.first_valid_id_from(msg_ids), 20);
});

test("update_email", () => {
    const terms = [
        {operator: "dm", operand: "steve@foo.com"},
        {operator: "sender", operand: "steve@foo.com"},
        {operator: "channel", operand: "steve@foo.com"}, // try to be tricky
    ];
    const filter = new Filter(terms);
    filter.update_email(steve.user_id, "showell@foo.com");
    assert.deepEqual(filter.operands("dm"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("sender"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("channel"), ["steve@foo.com"]);
});

function make_private_sub(name, stream_id) {
    const sub = {
        name,
        stream_id,
        invite_only: true,
    };
    stream_data.add_sub(sub);
}

function make_web_public_sub(name, stream_id) {
    const sub = {
        name,
        stream_id,
        is_web_public: true,
    };
    stream_data.add_sub(sub);
}

test("navbar_helpers", () => {
    const stream_id = 43;
    make_sub("Foo", stream_id);

    // make sure title has names separated with correct delimiters
    function properly_separated_names(names) {
        const names_internationalized = new Intl.ListFormat("en", {
            style: "long",
            type: "conjunction",
        }).format(names);
        return names_internationalized;
    }

    function test_redirect_url_with_search(test_case) {
        const terms = [...test_case.terms, {operator: "search", operand: "fizzbuzz"}];
        const filter = new Filter(terms);
        assert.equal(filter.generate_redirect_url(), test_case.redirect_url_with_search);
    }

    function test_common_narrow(test_case) {
        const filter = new Filter(test_case.terms);
        assert.equal(filter.is_common_narrow(), test_case.is_common_narrow);
    }

    function test_add_icon_data(test_case) {
        const filter = new Filter(test_case.terms);
        let context = {};
        context = filter.add_icon_data(context);
        assert.equal(context.icon, test_case.icon);
        assert.equal(context.zulip_icon, test_case.zulip_icon);
    }

    function test_get_title(test_case) {
        const filter = new Filter(test_case.terms);
        assert.deepEqual(filter.get_title(), test_case.title);
    }

    function test_helpers(test_case) {
        // debugging tip: add a `console.log(test_case)` here
        test_common_narrow(test_case);
        test_add_icon_data(test_case);
        test_get_title(test_case);
        test_redirect_url_with_search(test_case);
    }

    const sender = [{operator: "sender", operand: joe.email}];
    const guest_sender = [{operator: "sender", operand: alice.email}];
    const in_home = [{operator: "in", operand: "home"}];
    const in_all = [{operator: "in", operand: "all"}];
    const is_starred = [{operator: "is", operand: "starred"}];
    const is_dm = [{operator: "is", operand: "dm"}];
    const is_mentioned = [{operator: "is", operand: "mentioned"}];
    const is_resolved = [{operator: "is", operand: "resolved"}];
    const channels_public = [{operator: "channels", operand: "public"}];
    const channel_topic_terms = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    // foo channel exists
    const channel_term = [{operator: "channel", operand: "foo"}];
    make_private_sub("psub", "22");
    const private_channel_term = [{operator: "channel", operand: "psub"}];
    make_web_public_sub("webPublicSub", "12"); // capitalized just to try be tricky and robust.
    const web_public_channel = [{operator: "channel", operand: "webPublicSub"}];
    const non_existent_channel = [{operator: "channel", operand: "Elephant"}];
    const non_existent_channel_topic = [
        {operator: "channel", operand: "Elephant"},
        {operator: "topic", operand: "pink"},
    ];
    const dm = [{operator: "dm", operand: "joe@example.com"}];
    const dm_group = [{operator: "dm", operand: "joe@example.com,STEVE@foo.com"}];
    const dm_with_guest = [{operator: "dm", operand: "alice@example.com"}];
    const dm_group_including_guest = [
        {operator: "dm", operand: "alice@example.com,joe@example.com"},
    ];
    const dm_group_including_missing_person = [
        {operator: "dm", operand: "joe@example.com,STEVE@foo.com,sally@doesnotexist.com"},
    ];
    // not common narrows, but used for browser title updates
    const is_alerted = [{operator: "is", operand: "alerted"}];
    const is_unread = [{operator: "is", operand: "unread"}];
    const channel_topic_near = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "near", operand: "12"},
    ];
    const dm_near = [
        {operator: "dm", operand: "joe@example.com"},
        {operator: "near", operand: "12"},
    ];

    const test_cases = [
        {
            terms: sender,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages sent by " + joe.full_name,
            redirect_url_with_search: "/#narrow/sender/" + joe.user_id + "-joe",
        },
        {
            terms: guest_sender,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages sent by translated: alice (guest)",
            redirect_url_with_search: "/#narrow/sender/" + alice.user_id + "-alice",
        },
        {
            terms: is_starred,
            is_common_narrow: true,
            zulip_icon: "star-filled",
            title: "translated: Starred messages",
            redirect_url_with_search: "/#narrow/is/starred",
        },
        {
            terms: in_home,
            is_common_narrow: true,
            icon: "home",
            title: "translated: Combined feed",
            redirect_url_with_search: "#",
        },
        {
            terms: in_all,
            is_common_narrow: true,
            icon: "home",
            title: "translated: All messages including muted channels",
            redirect_url_with_search: "#",
        },
        {
            terms: is_dm,
            is_common_narrow: true,
            icon: "envelope",
            title: "translated: Direct message feed",
            redirect_url_with_search: "/#narrow/is/dm",
        },
        {
            terms: is_mentioned,
            is_common_narrow: true,
            zulip_icon: "at-sign",
            title: "translated: Mentions",
            redirect_url_with_search: "/#narrow/is/mentioned",
        },
        {
            terms: is_resolved,
            is_common_narrow: true,
            icon: "check",
            title: "translated: Topics marked as resolved",
            redirect_url_with_search: "/#narrow/topics/is/resolved",
        },
        {
            terms: channel_topic_terms,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "/#narrow/stream/43-Foo/topic/bar",
        },
        {
            terms: channels_public,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages in all public channels",
            redirect_url_with_search: "/#narrow/streams/public",
        },
        {
            terms: channel_term,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "/#narrow/stream/43-Foo",
        },
        {
            terms: non_existent_channel,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown channel #Elephant",
            redirect_url_with_search: "#",
        },
        {
            terms: non_existent_channel_topic,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown channel #Elephant",
            redirect_url_with_search: "#",
        },
        {
            terms: private_channel_term,
            is_common_narrow: true,
            zulip_icon: "lock",
            title: "psub",
            redirect_url_with_search: "/#narrow/stream/22-psub",
        },
        {
            terms: web_public_channel,
            is_common_narrow: true,
            zulip_icon: "globe",
            title: "webPublicSub",
            redirect_url_with_search: "/#narrow/stream/12-webPublicSub",
        },
        {
            terms: dm,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search:
                "/#narrow/dm/" + joe.user_id + "-" + parseOneAddress(joe.email).local,
        },
        {
            terms: dm_group,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([joe.full_name, steve.full_name]),
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + steve.user_id + "-group",
        },
        {
            terms: dm_with_guest,
            is_common_narrow: true,
            icon: "envelope",
            title: "translated: alice (guest)",
            redirect_url_with_search:
                "/#narrow/dm/" + alice.user_id + "-" + parseOneAddress(alice.email).local,
        },
        {
            terms: dm_group_including_guest,
            is_common_narrow: true,
            icon: "envelope",
            title: "translated: alice (guest) and joe",
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + alice.user_id + "-group",
        },
        {
            terms: dm_group_including_missing_person,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([
                joe.full_name,
                steve.full_name,
                "sally@doesnotexist.com",
            ]),
            redirect_url_with_search: "/#narrow/dm/undefined",
        },
        {
            terms: is_alerted,
            is_common_narrow: false,
            icon: undefined,
            title: "translated: Alerted messages",
            redirect_url_with_search: "#",
        },
        {
            terms: is_unread,
            is_common_narrow: false,
            icon: undefined,
            title: "translated: Unread messages",
            redirect_url_with_search: "#",
        },
        {
            terms: channel_topic_near,
            is_common_narrow: false,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "#",
        },
        {
            terms: dm_near,
            is_common_narrow: false,
            icon: "envelope",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search: "#",
        },
    ];

    realm.realm_enable_guest_user_indicator = true;

    for (const test_case of test_cases) {
        test_helpers(test_case);
    }

    // TODO: these may be removed, based on design decisions
    const sender_me = [{operator: "sender", operand: "me"}];
    const sender_joe = [{operator: "sender", operand: joe.email}];

    const redirect_edge_cases = [
        {
            terms: sender_me,
            redirect_url_with_search: "/#narrow/sender/" + me.user_id + "-Me-Myself",
            is_common_narrow: true,
        },
        {
            terms: sender_joe,
            redirect_url_with_search: "/#narrow/sender/" + joe.user_id + "-joe",
            is_common_narrow: true,
        },
    ];

    for (const test_case of redirect_edge_cases) {
        test_redirect_url_with_search(test_case);
    }

    // TODO: test every single one of the "ALL" redirects from the navbar behaviour table

    // incomplete and weak test cases just to restore coverage of filter.ts
    const complex_term = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "sender", operand: "me"},
    ];

    const redirect_url = "#";

    let filter = new Filter(complex_term);
    assert.equal(filter.generate_redirect_url(), redirect_url);
    assert.equal(filter.is_common_narrow(), false);

    const channel_topic_search_term = [
        {operator: "channel", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "potato"},
    ];

    const channel_topic_search_term_test_case = {
        terms: channel_topic_search_term,
        title: undefined,
    };

    test_get_title(channel_topic_search_term_test_case);

    realm.realm_enable_guest_user_indicator = false;
    const guest_user_test_cases_without_indicator = [
        {
            terms: guest_sender,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages sent by alice",
            redirect_url_with_search: "/#narrow/sender/" + alice.user_id + "-alice",
        },
        {
            terms: dm_with_guest,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([alice.full_name]),
            redirect_url_with_search:
                "/#narrow/dm/" + alice.user_id + "-" + parseOneAddress(alice.email).local,
        },
        {
            terms: dm_group_including_guest,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([alice.full_name, joe.full_name]),
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + alice.user_id + "-group",
        },
    ];

    for (const test_case of guest_user_test_cases_without_indicator) {
        test_helpers(test_case);
    }

    // this is actually wrong, but the code is currently not robust enough to throw an error here
    // also, used as an example of triggering last return statement.
    const default_redirect = {
        terms: [{operator: "channel", operand: "foo"}],
        redirect_url: "#",
    };

    filter = new Filter(default_redirect.terms);
    assert.equal(filter.generate_redirect_url(), default_redirect.redirect_url);
});

test("error_cases", () => {
    // This test just gives us 100% line coverage on defensive code that
    // should not be reached unless we break other code.

    const predicate = get_predicate([["dm", "Joe@example.com"]]);
    blueslip.expect("error", "Empty recipient list in message");
    assert.ok(!predicate({type: direct_message, display_recipient: []}));
});

run_test("is_spectator_compatible", () => {
    // tests same as test_is_spectator_compatible from test_message_fetch.py
    assert.ok(Filter.is_spectator_compatible([]));
    assert.ok(Filter.is_spectator_compatible([{operator: "has", operand: "attachment"}]));
    assert.ok(Filter.is_spectator_compatible([{operator: "has", operand: "image"}]));
    assert.ok(Filter.is_spectator_compatible([{operator: "search", operand: "magic"}]));
    assert.ok(Filter.is_spectator_compatible([{operator: "near", operand: "15"}]));
    assert.ok(
        Filter.is_spectator_compatible([
            {operator: "id", operand: "15"},
            {operator: "has", operand: "attachment"},
        ]),
    );
    assert.ok(Filter.is_spectator_compatible([{operator: "sender", operand: "hamlet@zulip.com"}]));
    assert.ok(!Filter.is_spectator_compatible([{operator: "dm", operand: "hamlet@zulip.com"}]));
    assert.ok(
        !Filter.is_spectator_compatible([{operator: "dm-including", operand: "hamlet@zulip.com"}]),
    );
    assert.ok(Filter.is_spectator_compatible([{operator: "channel", operand: "Denmark"}]));
    assert.ok(
        Filter.is_spectator_compatible([
            {operator: "channel", operand: "Denmark"},
            {operator: "topic", operand: "logic"},
        ]),
    );
    assert.ok(!Filter.is_spectator_compatible([{operator: "is", operand: "starred"}]));
    assert.ok(!Filter.is_spectator_compatible([{operator: "is", operand: "dm"}]));
    assert.ok(Filter.is_spectator_compatible([{operator: "channels", operand: "public"}]));

    // Malformed input not allowed
    assert.ok(!Filter.is_spectator_compatible([{operator: "has"}]));

    // "is:private" was renamed to "is:dm"
    assert.ok(!Filter.is_spectator_compatible([{operator: "is", operand: "private"}]));
    // "pm-with" was renamed to "dm"
    assert.ok(
        !Filter.is_spectator_compatible([{operator: "pm-with", operand: "hamlet@zulip.com"}]),
    );
    // "stream" was renamted to "channel"
    assert.ok(Filter.is_spectator_compatible([{operator: "stream", operand: "Denmark"}]));
    // "streams" was renamed to "channels"
    assert.ok(Filter.is_spectator_compatible([{operator: "streams", operand: "public"}]));
    // "group-pm-with:" was replaced with "dm-including:"
    assert.ok(
        !Filter.is_spectator_compatible([{operator: "group-pm-with", operand: "hamlet@zulip.com"}]),
    );
});

run_test("is_in_home", () => {
    const filter = new Filter([{operator: "in", operand: "home"}]);
    assert.ok(filter.is_in_home());

    const filter2 = new Filter([{operator: "in", operand: "all"}]);
    assert.ok(!filter2.is_in_home());

    // Test home with additional terms is not all messages.
    const filter3 = new Filter([
        {operator: "in", operand: "home"},
        {operator: "topic", operand: "foo"},
    ]);
    assert.ok(!filter3.is_in_home());
});

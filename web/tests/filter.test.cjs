"use strict";

const assert = require("node:assert/strict");

const {parseOneAddress} = require("email-addresses");

const {mock_esm, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const blueslip = require("./lib/zblueslip.cjs");
const $ = require("./lib/zjquery.cjs");
const {page_params} = require("./lib/zpage_params.cjs");

const message_store = mock_esm("../src/message_store");
const user_topics = mock_esm("../src/user_topics");

const resolved_topic = zrequire("../shared/src/resolved_topic");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const {Filter} = zrequire("../src/filter");
const {set_current_user, set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");
const muted_users = zrequire("muted_users");

const realm = {};
set_realm(realm);
const current_user = {};
set_current_user(current_user);
initialize_user_settings({user_settings: {}});

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

const jeff = {
    email: "jeff@foo.com",
    user_id: 34,
    full_name: "jeff",
};

const annie = {
    email: "annie@foo.com",
    user_id: 35,
    full_name: "annie",
    is_guest: true,
};

people.add_active_user(me);
people.add_active_user(joe);
people.add_active_user(steve);
people.add_active_user(alice);
people.add_active_user(jeff);
people.add_active_user(annie);
people.initialize_current_user(me.user_id);
muted_users.add_muted_user(jeff.user_id);
muted_users.add_muted_user(annie.user_id);

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

let _stream_id = 0;
function new_stream_id() {
    _stream_id += 1;
    return _stream_id;
}

const foo_stream_id = new_stream_id();
const foo_sub = {
    name: "Foo",
    stream_id: foo_stream_id,
};

const general_sub = {
    name: "general",
    stream_id: new_stream_id(),
};
stream_data.add_sub(general_sub);

const invalid_sub_id = new_stream_id();

function test(label, f) {
    run_test(label, (helpers) => {
        stream_data.clear_subscriptions();
        f(helpers);
    });
}

test("basics", () => {
    let terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "channel", operand: invalid_sub_id.toString(), negated: true}, // excluded
        {operator: "topic", operand: "bar"},
    ];
    let filter = new Filter(terms);

    assert_same_terms(filter.terms(), terms);
    assert.deepEqual(filter.operands("channel"), [foo_stream_id.toString()]);

    assert.ok(filter.has_operator("channel"));
    assert.ok(!filter.has_operator("search"));

    assert.ok(filter.has_operand("channel", foo_stream_id.toString()));
    assert.ok(!filter.has_operand("channel", invalid_sub_id.toString()));

    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.can_show_next_unread_topic_conversation_button());
    assert.ok(!filter.can_show_next_unread_dm_conversation_button());

    assert.ok(filter.can_bucket_by("channel"));
    assert.ok(filter.can_bucket_by("channel", "topic"));
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // "stream" was renamed to "channel"
    terms = [{operator: "stream", operand: foo_stream_id.toString()}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("channel"));
    assert.deepEqual(filter.operands("channel"), [foo_stream_id.toString()]);
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.can_show_next_unread_topic_conversation_button());
    assert.ok(!filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "channel", operand: invalid_sub_id.toString(), negated: true}, // excluded
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(terms);

    assert.deepEqual(filter.operands("channel"), [foo_stream_id.toString()]);

    assert.ok(filter.has_operator("channel"));
    assert.ok(!filter.has_operator("search"));

    assert.ok(filter.has_operand("channel", foo_stream_id.toString()));
    assert.ok(!filter.has_operand("channel", invalid_sub_id.toString()));

    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "pizza"},
    ];
    filter = new Filter(terms);

    assert.ok(filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.can_bucket_by("channel"));
    assert.ok(filter.can_bucket_by("channel", "topic"));
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "near", operand: 17},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.can_bucket_by("channel"));
    assert.ok(filter.can_bucket_by("channel", "topic"));
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(filter.can_show_next_unread_topic_conversation_button());
    assert.ok(!filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // If our only channel operator is negated, then for all intents and purposes,
    // we don't consider ourselves to have a channel operator, because we don't
    // want to have the channel in the tab bar or unsubscribe messaging, etc.
    terms = [{operator: "channel", operand: invalid_sub_id.toString(), negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("channel"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // Negated searches are just like positive searches for our purposes, since
    // the search logic happens on the backend and we need to have can_apply_locally()
    // be false, and we want "Search results" in the tab bar.
    terms = [{operator: "search", operand: "stop_word", negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.has_operator("search"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.contains_no_partial_conversations());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.can_show_next_unread_topic_conversation_button());
    assert.ok(!filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // Similar logic applies to negated "has" searches.
    terms = [{operator: "has", operand: "images", negated: true}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("has"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.can_apply_locally(true));
    assert.ok(!filter.includes_full_stream_history());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.contains_no_partial_conversations());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "channels", operand: "public", negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("channels"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(filter.has_negated_operand("channels", "public"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "channels", operand: "public"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.has_operator("channels"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.has_negated_operand("channels", "public"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // "streams" was renamed to "channels"
    terms = [{operator: "streams", operand: "public"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("channels"));
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "is", operand: "dm"}];
    filter = new Filter(terms);
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.can_show_next_unread_topic_conversation_button());
    assert.ok(filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "is", operand: "dm", negated: true}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.can_show_next_unread_topic_conversation_button());
    assert.ok(!filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // "is:private" was renamed to "is:dm"
    terms = [{operator: "is", operand: "private"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operand("is", "dm"));
    assert.ok(!filter.has_operand("is", "private"));
    assert.ok(!filter.can_show_next_unread_topic_conversation_button());
    assert.ok(filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.contains_no_partial_conversations());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.can_show_next_unread_topic_conversation_button());
    assert.ok(!filter.can_show_next_unread_dm_conversation_button());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "is", operand: "starred"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.contains_no_partial_conversations());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "dm", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(filter.is_non_group_direct_message());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
    assert.ok(!filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "dm", operand: "joe@example.com"},
        {operator: "near", operand: 17},
    ];
    filter = new Filter(terms);
    assert.ok(filter.is_non_group_direct_message());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "dm", operand: "joe@example.com,jack@example.com"}];
    filter = new Filter(terms);
    assert.ok(!filter.is_non_group_direct_message());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
    assert.ok(!filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "dm", operand: "joe@example.com,jack@example.com"},
        {operator: "with", operand: "12"},
    ];
    filter = new Filter(terms);
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
    assert.ok(!filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // "pm-with" was renamed to "dm"
    terms = [{operator: "pm-with", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("dm"));
    assert.ok(!filter.has_operator("    pm-with"));
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "dm-including", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(!filter.is_non_group_direct_message());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // "group-pm-with" was replaced with "dm-including"
    terms = [{operator: "group-pm-with", operand: "joe@example.com"}];
    filter = new Filter(terms);
    assert.ok(filter.has_operator("dm-including"));
    assert.ok(!filter.has_operator("group-pm-with"));
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [{operator: "is", operand: "resolved"}];
    filter = new Filter(terms);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // Highly complex query to exercise
    // filter.contains_no_partial_conversations loop.
    terms = [
        {operator: "is", operand: "resolved", negated: true},
        {operator: "is", operand: "followed", negated: true},
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
    assert.ok(filter.contains_no_partial_conversations());
    // This next check verifies what is probably a bug; see the
    // comment in the can_apply_locally implementation.
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
    assert.ok(!filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "with", operand: 17},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
    assert.ok(filter.can_bucket_by("channel", "topic", "with"));
    assert.ok(!filter.is_conversation_view_with_near());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    // "stream" was renamed to "channel"
    terms = [
        {operator: "stream", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(terms);

    assert.ok(!filter.is_keyword_search());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
    assert.ok(!filter.is_conversation_view_with_near());
    assert.ok(!filter.is_channel_view());
    assert.ok(filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: "channel_name"},
        {operator: "channels", operand: "public"},
        {operator: "topic", operand: "patience"},
    ];
    filter = new Filter(terms);
    assert.ok(!filter.is_keyword_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.contains_no_partial_conversations());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());
    assert.ok(!filter.may_contain_multiple_conversations());
    assert.ok(!filter.is_channel_view());
    assert.ok(!filter.has_exactly_channel_topic_operators());

    terms = [
        {operator: "channel", operand: "foo", negated: false},
        {operator: "topic", operand: "bar", negated: false},
    ];
    filter = new Filter(terms);

    assert.equal(filter.has_exactly_channel_topic_operators(), true);

    filter.adjust_with_operand_to_message(12);

    assert.deepEqual(filter.terms(), [...terms, {operator: "with", operand: "12"}]);
    assert.equal(filter.has_exactly_channel_topic_operators(), false);

    terms = [{operator: "channel", operand: "foo", negated: false}];
    filter = new Filter(terms);
    assert.ok(filter.is_channel_view());
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

    has_link_term = [{operator: "has", operand: "reaction"}];
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

    is_operator = [{operator: "is", operand: "followed", negated: true}];
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

    const channel_term = [{operator: "channel", operand: foo_stream_id.toString()}];
    let filter = new Filter(channel_term);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(channel_term);
    assert_not_mark_read_with_is_operands(channel_term);
    assert_not_mark_read_when_searching(channel_term);

    const channel_negated_operator = [{operator: "channel", operand: foo_stream_id, negated: true}];
    filter = new Filter(channel_negated_operator);
    assert.ok(!filter.can_mark_messages_read());

    const channel_topic_terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(channel_topic_terms);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(channel_topic_terms);
    assert_not_mark_read_with_is_operands(channel_topic_terms);
    assert_not_mark_read_when_searching(channel_topic_terms);

    const channel_negated_topic_terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
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

    const is_muted = [{operator: "is", operand: "muted"}];
    const is_muted_negated = [{operator: "is", operand: "muted", negated: true}];
    filter = new Filter(is_muted);
    assert.ok(!filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(is_muted);
    assert_not_mark_read_with_has_operands(is_muted);
    assert_not_mark_read_when_searching(is_muted);
    filter = new Filter(is_muted_negated);
    assert.ok(filter.can_mark_messages_read());

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

    terms = [{operator: "is", operand: "starred"}];
    filter = new Filter(terms);
    assert.ok(!filter.allow_use_first_unread_when_narrowing());

    // Side case
    terms = [{operator: "is", operand: "any"}];
    filter = new Filter(terms);
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
});

test("filter_with_new_params_topic", () => {
    const terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(terms);

    assert.ok(filter.has_topic(foo_stream_id.toString(), "old topic"));
    assert.ok(!filter.has_topic(invalid_sub_id.toString(), "old topic"));
    assert.ok(!filter.has_topic(foo_stream_id.toString(), "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "topic",
        operand: "new topic",
    });

    assert.deepEqual(new_filter.operands("channel"), [foo_stream_id.toString()]);
    assert.deepEqual(new_filter.operands("topic"), ["new topic"]);
});

test("filter_with_new_params_channel", () => {
    const terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(terms);

    assert.ok(filter.has_topic(foo_stream_id.toString(), "old topic"));
    assert.ok(!filter.has_topic(invalid_sub_id.toString(), "old topic"));
    assert.ok(!filter.has_topic(foo_stream_id.toString(), "wrong"));

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
        operand: foo_stream_id.toString(),
    };
    const terms = [term];
    const filter = new Filter(terms);

    assert.deepEqual(filter.operands("channel"), [foo_stream_id.toString()]);
    assert.ok(filter.can_bucket_by("channel"));
});

test("public_terms", ({override, override_rewire}) => {
    stream_data.clear_subscriptions();
    const some_channel_id = new_stream_id();
    let terms = [
        {operator: "channel", operand: some_channel_id},
        {operator: "in", operand: "all"},
        {operator: "topic", operand: "bar"},
    ];
    let filter = new Filter(terms);
    const expected_terms = [
        {operator: "channel", operand: some_channel_id},
        {operator: "in", operand: "all"},
        {operator: "topic", operand: "bar"},
    ];
    override(page_params, "narrow_stream", undefined);
    override_rewire(stream_data, "get_sub_by_name", (name) => {
        assert.equal(name, "default");
        return {
            name,
            some_channel_id,
        };
    });
    assert_same_terms(filter.public_terms(), expected_terms);
    assert.ok(filter.can_bucket_by("channel"));

    terms = [{operator: "channel", operand: some_channel_id}];
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
    assert.equal(term.operand, "fOO");

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

    term = Filter.canonicalize_term({operator: "has", operand: "reactions"});
    assert.equal(term.operator, "has");
    assert.equal(term.operand, "reaction");
});

test("ensure_channel_topic_terms", () => {
    const channel_term = {operator: "channel", operand: `${general_sub.stream_id}`};
    const topic_term = {operator: "topic", operand: "discussion"};

    const message = {
        type: "stream",
        id: 12,
        stream_id: general_sub.stream_id,
        display_recipient: "general",
        topic: "discussion",
    };

    const term_1 = Filter.ensure_channel_topic_terms(
        [{operator: "with", operand: message.id}],
        message,
    );
    const term_2 = Filter.ensure_channel_topic_terms(
        [topic_term, {operator: "with", operand: message.id}],
        message,
    );
    const term_3 = Filter.ensure_channel_topic_terms(
        [channel_term, {operator: "with", operand: message.id}],
        message,
    );
    const term_4 = Filter.ensure_channel_topic_terms(
        [
            {operator: "dm", operand: "foo@example.com"},
            {operator: "with", operand: message.id},
        ],
        message,
    );
    const term_5 = Filter.ensure_channel_topic_terms(
        [{operator: "with", operand: message.id}],
        message,
    );

    const terms = [term_1, term_2, term_3, term_4, term_5];

    for (const term of terms) {
        assert.deepEqual(term, [channel_term, topic_term, {operator: "with", operand: 12}]);
    }
});

test("predicate_basics", ({override}) => {
    // Predicates are functions that accept a message object with the message
    // attributes (not content), and return true if the message belongs in a
    // given narrow. If the narrow parameters include a search, the predicate
    // passes through all messages.
    //
    // To keep these tests simple, we only pass objects with a few relevant attributes
    // rather than full-fledged message objects.

    stream_data.add_sub(foo_sub);
    let predicate = get_predicate([
        ["channel", foo_stream_id.toString()],
        ["topic", "Bar"],
    ]);

    assert.ok(predicate({type: stream_message, stream_id: foo_stream_id, topic: "bar"}));
    assert.ok(!predicate({type: stream_message, stream_id: foo_stream_id, topic: "whatever"}));
    // 9999999 doesn't exist, testing no match
    assert.ok(!predicate({type: stream_message, stream_id: 9999999}));
    assert.ok(!predicate({type: direct_message}));

    // For old channels that we are no longer subscribed to, we may not have
    // a subscription, but these should still match by channel name.
    const old_sub_id = new_stream_id();
    const old_sub = {
        name: "old-subscription",
        stream_id: old_sub_id,
        subscribed: false,
    };
    stream_data.add_sub(old_sub);
    predicate = get_predicate([
        ["channel", old_sub_id.toString()],
        ["topic", "Bar"],
    ]);
    assert.ok(predicate({type: stream_message, stream_id: old_sub.stream_id, topic: "bar"}));
    // 99999 doesn't exist, testing no match
    assert.ok(!predicate({type: stream_message, stream_id: invalid_sub_id, topic: "whatever"}));

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

    predicate = get_predicate([["is", "followed"]]);

    override(user_topics, "is_topic_followed", () => false);
    assert.ok(!predicate({type: "stream", topic: "foo", stream_id: 5}));

    override(user_topics, "is_topic_followed", () => true);
    assert.ok(predicate({type: "stream", topic: "foo", stream_id: 5}));

    const unknown_stream_id = new_stream_id();
    override(user_topics, "is_topic_visible_in_home", () => false);
    predicate = get_predicate([["in", "home"]]);
    assert.ok(!predicate({stream_id: unknown_stream_id, stream: "unknown"}));
    assert.ok(predicate({type: direct_message}));

    // Muted topic is not part of in-home.
    with_overrides(({override}) => {
        override(user_topics, "is_topic_visible_in_home", () => false);
        assert.ok(!predicate({stream_id: foo_stream_id, topic: "bar"}));
    });

    // Muted stream is not part of in-home.
    const muted_stream = {
        stream_id: 94924,
        name: "muted",
        is_muted: true,
    };
    stream_data.add_sub(muted_stream);
    assert.ok(!predicate({stream_id: muted_stream.stream_id, topic: "bar"}));

    // Muted stream but topic is unmuted or followed is part of in-home.
    with_overrides(({override}) => {
        override(user_topics, "is_topic_visible_in_home", () => true);
        assert.ok(predicate({stream_id: muted_stream.stream_id, topic: "bar"}));
    });

    make_sub("kiosk", 1234);
    with_overrides(({override}) => {
        override(page_params, "narrow_stream", "kiosk");
        assert.ok(predicate({stream_id: 1234}));
    });

    override(user_topics, "is_topic_visible_in_home", () => false);
    predicate = get_predicate([["is", "muted"]]);
    assert.ok(predicate({stream_id: unknown_stream_id, stream: "unknown"}));
    assert.ok(!predicate({type: direct_message}));

    // Muted topic is a part of is-muted.
    with_overrides(({override}) => {
        override(user_topics, "is_topic_visible_in_home", () => false);
        assert.ok(predicate({stream_id: foo_stream_id, topic: "bar"}));
    });

    // Muted stream is a part of is:muted.
    assert.ok(predicate({stream_id: muted_stream.stream_id, topic: "bar"}));

    // Muted stream but topic is unmuted or followed is not a part of is-muted.
    with_overrides(({override}) => {
        override(user_topics, "is_topic_visible_in_home", () => true);
        assert.ok(!predicate({stream_id: muted_stream.stream_id, topic: "bar"}));
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

    const clean_reactions_message = {
        clean_reactions: new Map(
            Object.entries({
                "unicode_emoji,1f3b1": {
                    class: "message_reaction reacted",
                    count: 2,
                    emoji_alt_code: false,
                    emoji_code: "1f3b1",
                    emoji_name: "8ball",
                    is_realm_emoji: false,
                    label: "translated: You (click to remove) and Bob van Roberts reacted with :8ball:",
                    local_id: "unicode_emoji,1f3b1",
                    reaction_type: "unicode_emoji",
                    user_ids: [alice.user_id],
                    vote_text: "translated: You, Bob van Roberts",
                },
            }),
        ),
    };

    const non_reaction_msg = {
        clean_reactions: new Map(),
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

    const has_reaction = get_predicate([["has", "reaction"]]);
    assert.ok(has_reaction(clean_reactions_message));
    assert.ok(!has_reaction(non_reaction_msg));
});

test("negated_predicates", () => {
    let predicate;
    let narrow;

    const social_stream_id = new_stream_id();
    make_sub("social", social_stream_id);

    narrow = [{operator: "channel", operand: social_stream_id.toString(), negated: true}];
    predicate = new Filter(narrow).predicate();
    assert.ok(predicate({type: stream_message, stream_id: 999999}));
    assert.ok(!predicate({type: stream_message, stream_id: social_stream_id}));

    narrow = [{operator: "channels", operand: "public", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert.ok(predicate({}));
});

function test_mit_exceptions() {
    const foo_stream_id = new_stream_id();
    make_sub("Foo", foo_stream_id);
    let predicate = get_predicate([
        ["channel", foo_stream_id.toString()],
        ["topic", "personal"],
    ]);
    assert.ok(predicate({type: stream_message, stream_id: foo_stream_id, topic: "personal"}));
    assert.ok(predicate({type: stream_message, stream_id: foo_stream_id, topic: ""}));
    // 9999 doesn't correspond to any channel
    assert.ok(!predicate({type: stream_message, stream_id: 9999}));
    assert.ok(!predicate({type: stream_message, stream_id: foo_stream_id, topic: "whatever"}));
    assert.ok(!predicate({type: direct_message}));

    predicate = get_predicate([
        ["channel", foo_stream_id.toString()],
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
        {operator: "channel", operand: foo_stream_id.toString()},
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
    const stream_id = new_stream_id();
    make_sub("Off topic", stream_id);
    const terms = [
        {operator: "channel", operand: stream_id.toString()},
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

    function _test(for_pills = false) {
        const result = Filter.parse(string, for_pills);
        assert_same_terms(result, terms);
    }

    make_sub(foo_sub.name, foo_stream_id);
    string = "channel:Foo topic:bar yo";
    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "yo"},
    ];
    _test();

    string = `channel:${foo_stream_id} topic:bar yo`;
    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "yo"},
    ];
    _test();

    // "stream" was renamed to "channel"
    string = `stream:${foo_stream_id} topic:Bar yo`;
    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
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

    string = "sender:me";
    terms = [{operator: "sender", operand: `${me.email}`}];
    _test(true);

    string = "-sender:me";
    terms = [{operator: "sender", operand: `${me.email}`, negated: true}];
    _test(true);

    string = "https://www.google.com";
    terms = [{operator: "search", operand: "https://www.google.com"}];
    _test();

    string = `channel:${foo_stream_id} -channel:${invalid_sub_id}`;
    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "channel", operand: invalid_sub_id.toString(), negated: true},
    ];
    _test();

    string = `text channel:${foo_stream_id} more text`;
    terms = [
        {operator: "search", operand: "text"},
        {operator: "channel", operand: foo_stream_id.toString()},
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
    terms = [{operator: "channels", operand: "public"}];
    _test();

    string = `channel:${foo_stream_id} :emoji: are cool`;
    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "search", operand: ":emoji: are cool"},
    ];
    _test();

    string = `:channel: channel:${foo_stream_id} :emoji: are cool`;
    terms = [
        {operator: "search", operand: ":channel:"},
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "search", operand: ":emoji: are cool"},
    ];
    _test();

    string = `:channel: channel:${foo_stream_id} -:emoji: are cool`;
    terms = [
        {operator: "search", operand: ":channel:"},
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "search", operand: "-:emoji: are cool"},
    ];
    _test();

    string = "";
    terms = [];
    _test();

    string = `channel: ${foo_stream_id} topic: "separated with space"`;
    terms = [
        {operator: "channel", operand: ""},
        {operator: "search", operand: foo_stream_id.toString()},
        {operator: "topic", operand: ""},
        {operator: "search", operand: '"separated with space"'},
    ];
    _test();

    string = `topic: is:starred`;
    terms = [
        {operator: "topic", operand: ""},
        {operator: "is", operand: "starred"},
    ];
    _test();
});

test("unparse", () => {
    let string;
    let terms;

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "Bar", negated: true},
        {operator: "search", operand: "yo"},
    ];
    string = `channel:${foo_stream_id} -topic:Bar yo`;
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
        {operator: "stream", operand: foo_stream_id.toString()},
        {operator: "subject", operand: "Bar"},
    ];
    string = `channel:${foo_stream_id} topic:Bar`;
    assert.deepEqual(Filter.unparse(terms), string);

    terms = [
        {operator: "dm", operand: '\t "%+.\u00A0'},
        {operator: "topic", operand: '\t "%+.\u00A0'},
    ];
    string = "dm:%09%20%22%25+.%C2%A0 topic:%09+%22%25%2B.%C2%A0";
    assert.equal(Filter.unparse(terms), string);
    assert_same_terms(Filter.parse(string), terms);
});

test("describe", ({mock_template, override}) => {
    let narrow;
    let string;
    mock_template("search_description.hbs", true, (_data, html) => html);

    narrow = [{operator: "channels", operand: "public"}];
    string = "all public channels";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "channels", operand: "public", negated: true}];
    string = "exclude all public channels";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    page_params.is_spectator = true;
    narrow = [{operator: "channels", operand: "public"}];
    string = "all public channels that you can view";
    assert.equal(Filter.search_description_as_html(narrow, false), string);
    page_params.is_spectator = false;

    const devel_id = new_stream_id();
    make_sub("devel", devel_id);

    narrow = [
        {operator: "channel", operand: devel_id.toString()},
        {operator: "is", operand: "starred"},
    ];
    string = "messages in #devel, starred messages";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    const river_id = new_stream_id();
    make_sub("river", river_id);
    narrow = [
        {operator: "channel", operand: river_id.toString()},
        {operator: "is", operand: "unread"},
    ];
    string = "messages in #river, unread messages";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "channel", operand: devel_id.toString()},
        {operator: "topic", operand: "JS"},
    ];
    string = "messages in #devel > JS";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "is", operand: "dm"},
        {operator: "search", operand: "lunch"},
    ];
    string = "direct messages, search for lunch";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "id", operand: 99}];
    string = "message ID 99";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "in", operand: "home"}];
    string = "messages in home";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "is", operand: "mentioned"}];
    string = "messages that mention you";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "is", operand: "alerted"}];
    string = "alerted messages";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "is", operand: "resolved"}];
    string = "resolved topics";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "is", operand: "followed"}];
    string = "followed topics";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "is", operand: "muted"}];
    string = "muted messages";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    // operands with their own negative words, like resolved.
    narrow = [{operator: "is", operand: "resolved", negated: true}];
    string = "unresolved topics";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "is", operand: "something_we_do_not_support"}];
    string = "invalid something_we_do_not_support operand for is operator";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    // this should be unreachable, but just in case
    narrow = [{operator: "bogus", operand: "foo"}];
    string = "unknown operator";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "channel", operand: devel_id.toString()},
        {operator: "topic", operand: "JS", negated: true},
    ];
    string = "messages in #devel, exclude topic JS";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "is", operand: "dm"},
        {operator: "search", operand: "lunch", negated: true},
    ];
    string = "direct messages, exclude lunch";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "channel", operand: devel_id.toString()},
        {operator: "is", operand: "starred", negated: true},
    ];
    string = "messages in #devel, exclude starred messages";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "channel", operand: devel_id.toString()},
        {operator: "has", operand: "image", negated: true},
    ];
    string = "messages in #devel, exclude messages with images";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "has", operand: "abc", negated: true},
        {operator: "channel", operand: devel_id.toString()},
    ];
    string = "invalid abc operand for has operator, messages in #devel";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "has", operand: "image", negated: true},
        {operator: "channel", operand: devel_id.toString()},
    ];
    string = "exclude messages with images, messages in #devel";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [];
    string = "combined feed";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    // canonical version of the operator is used in description
    narrow = [
        {operator: "stream", operand: devel_id.toString()},
        {operator: "subject", operand: "JS", negated: true},
    ];
    string = "messages in #devel, exclude topic JS";
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    // Empty string topic involved.
    override(realm, "realm_empty_topic_display_name", "general chat");
    narrow = [
        {operator: "channel", operand: devel_id.toString()},
        {operator: "topic", operand: ""},
    ];
    string =
        'messages in #devel > <span class="empty-topic-display">translated: general chat</span>';
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [
        {operator: "topic", operand: ""},
        {operator: "is", operand: "starred"},
    ];
    string =
        'topic <span class="empty-topic-display">translated: general chat</span>, starred messages';
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "topic", operand: ""}];
    string = `topic <span class="empty-topic-display">translated: general chat</span>`;
    assert.equal(Filter.search_description_as_html(narrow, false), string);

    narrow = [{operator: "topic", operand: ""}];
    string = "topic ";
    assert.equal(Filter.search_description_as_html(narrow, true), string);
});

test("can_bucket_by", () => {
    const channel_id = new_stream_id();
    make_sub("My channel", channel_id);
    let terms = [{operator: "channel", operand: channel_id.toString()}];
    let filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), true);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [
        // try a non-orthodox ordering
        {operator: "topic", operand: "My topic"},
        {operator: "channel", operand: channel_id.toString()},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), true);
    assert.equal(filter.can_bucket_by("channel", "topic"), true);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [
        {operator: "channel", operand: channel_id.toString(), negated: true},
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
    assert.equal(filter.can_bucket_by("dm", "with"), false);

    terms = [{operator: "dm", operand: "foo@example.com,bar@example.com"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), false);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), true);
    assert.equal(filter.can_bucket_by("dm", "with"), false);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-dm"), false);

    terms = [
        {operator: "dm", operand: "foo@example.com,bar@example.com"},
        {operator: "with", operand: "7"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("channel"), false);
    assert.equal(filter.can_bucket_by("channel", "topic"), false);
    assert.equal(filter.can_bucket_by("dm", "with"), true);
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

    assert_term_sort(["topic", "channel", "with"], ["channel", "topic", "with"]);

    assert_term_sort(["bogus", "channel", "topic"], ["channel", "topic", "bogus"]);
    assert_term_sort(["channel", "topic", "channel"], ["channel", "channel", "topic"]);

    assert_term_sort(["search", "channels-public"], ["channels-public", "search"]);

    const terms = [
        {operator: "topic", operand: "lunch"},
        {operator: "sender", operand: "steve@foo.com"},
        {operator: "channel", operand: new_stream_id().toString()},
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

test("is_valid_search_term", () => {
    const denmark = {
        stream_id: 100,
        name: "Denmark",
    };
    stream_data.add_sub(denmark);

    const test_data = [
        ["has:image", true],
        ["has:nonsense", false],
        ["is:unread", true],
        ["is:nonsense", false],
        ["in:home", true],
        ["in:nowhere", false],
        ["id:4", true],
        ["near:home", false],
        ["channel:" + denmark.stream_id, true],
        [`channel:${invalid_sub_id}`, false],
        ["channels:public", true],
        ["channels:private", false],
        ["topic:GhostTown", true],
        ["dm-including:alice@example.com", true],
        ["sender:ghost@zulip.com", false],
        ["sender:me", true],
        ["dm:alice@example.com,ghost@example.com", false],
        ["dm:alice@example.com,joe@example.com", true],
    ];
    for (const [search_term_string, expected_is_valid] of test_data) {
        assert.equal(
            Filter.is_valid_search_term(Filter.parse(search_term_string)[0]),
            expected_is_valid,
        );
    }

    blueslip.expect("error", "Unexpected search term operator: foo");
    assert.equal(
        Filter.is_valid_search_term({
            operator: "foo",
            operand: "bar",
        }),
        false,
    );
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

test("try_adjusting_for_moved_with_target", ({override}) => {
    const scotland_id = new_stream_id();
    make_sub("Scotland", scotland_id);
    const verona_id = new_stream_id();
    make_sub("Verona", verona_id);
    const messages = {
        12: {
            type: "stream",
            stream_id: scotland_id,
            display_recipient: "Scotland",
            topic: "Test 1",
            id: 12,
        },
        17: {
            type: "stream",
            stream_id: verona_id,
            display_recipient: "Verona",
            topic: "Test 2",
            id: 17,
        },
        2: {type: "direct", id: 2, display_recipient: [{id: 3, email: "user3@zulip.com"}]},
    };

    override(message_store, "get", (msg_id) => messages[msg_id]);

    // When the narrow terms are correct, it returns the same terms
    let terms = [
        {operator: "channel", operand: scotland_id.toString(), negated: false},
        {operator: "topic", operand: "Test 1", negated: false},
        {operator: "with", operand: "12", negated: false},
    ];

    let filter = new Filter(terms);
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, true);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, false);
    assert.deepEqual(filter.terms(), terms);

    // When the narrow terms are incorrect, the narrow is corrected
    // to the narrow of the `with` operand.
    const incorrect_terms = [
        {operator: "channel", operand: verona_id.toString(), negated: false},
        {operator: "topic", operand: "Test 2", negated: false},
        {operator: "with", operand: "12", negated: false},
    ];

    filter = new Filter(incorrect_terms);
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, true);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, false);
    assert.deepEqual(filter.terms(), terms);

    // when message specified in `with` operator does not exist in
    // message_store, we rather go to the server, without any updates.
    terms = [
        {operator: "channel", operand: scotland_id.toString(), negated: false},
        {operator: "topic", operand: "Test 1", negated: false},
        {operator: "with", operand: "11", negated: false},
    ];

    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, true);
    assert.deepEqual(filter.terms(), terms);

    // When the narrow consists of `channel` or `topic` operators, while
    // the `with` operator corresponds to that of a direct message, then
    // the narrow is adjusted to point to the narrow containing the message.
    terms = [
        {operator: "channel", operand: scotland_id.toString(), negated: false},
        {operator: "topic", operand: "Test 1", negated: false},
        {operator: "with", operand: "2", negated: false},
    ];
    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, false);
    assert.deepEqual(filter.terms(), [
        {operator: "dm", operand: "user3@zulip.com", negated: false},
        {operator: "with", operand: "2", negated: false},
    ]);

    // When the narrow consists of `dm` operators, while the `with`
    // operator corresponds to that of a channel topic message.
    terms = [
        {operator: "dm", operand: "iago@foo.com"},
        {operator: "with", operand: "12"},
    ];
    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.requires_adjustment_for_moved_with_target, false);
    assert.deepEqual(filter.terms(), [
        {operator: "channel", operand: scotland_id.toString(), negated: false},
        {operator: "topic", operand: "Test 1", negated: false},
        {operator: "with", operand: "12", negated: false},
    ]);

    // When message id attached to `with` operator is found locally,
    // and is present in the same narrow as the original one, then
    // no hash change is required.
    terms = [
        {operator: "channel", operand: verona_id.toString(), negated: false},
        {operator: "topic", operand: "Test 2", negated: false},
        {operator: "with", operand: "17", negated: false},
    ];
    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.narrow_requires_hash_change, false);

    // When message id attached to `with` operator is not found
    // locally, but messages fetched are in same narrow as
    // original narrow, then no hash change is required.
    terms = [
        {operator: "channel", operand: verona_id.toString(), negated: false},
        {operator: "topic", operand: "Test 2", negated: false},
        {operator: "with", operand: "1", negated: false},
    ];
    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    // now messages are fetched from server, and a single
    // fetched message is used to adjust narrow terms.
    filter.try_adjusting_for_moved_with_target(messages["17"]);
    assert.deepEqual(filter.narrow_requires_hash_change, false);

    // When message id attached to `with` operator is found locally,
    // and is not present in the same narrow as the original one,
    // then hash change is required.
    terms = [
        {operator: "channel", operand: verona_id.toString(), negated: false},
        {operator: "topic", operand: "Test 2", negated: false},
        {operator: "with", operand: "12", negated: false},
    ];
    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    assert.deepEqual(filter.narrow_requires_hash_change, true);

    // When message id attached to `with` operator is not found
    // locally, and messages fetched are in different narrow from
    // original narrow, then hash change is required.
    terms = [
        {operator: "channel", operand: verona_id.toString(), negated: false},
        {operator: "topic", operand: "Test 2", negated: false},
        {operator: "with", operand: "1", negated: false},
    ];
    filter = new Filter(terms);
    filter.try_adjusting_for_moved_with_target();
    // now messages are fetched from server, and a single
    // fetched message is used to adjust narrow terms.
    filter.try_adjusting_for_moved_with_target(messages["12"]);
    assert.deepEqual(filter.narrow_requires_hash_change, true);
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

function make_archived_sub(name, stream_id) {
    const sub = {
        name,
        stream_id,
        is_archived: true,
    };
    stream_data.add_sub(sub);
}

test("navbar_helpers", ({override}) => {
    stream_data.add_sub(foo_sub);

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

    function test_get_description(test_case) {
        const filter = new Filter(test_case.terms);
        const description = filter.get_description();

        if (test_case.description !== undefined && test_case.link !== undefined) {
            assert.deepEqual(description, {
                description: test_case.description,
                link: test_case.link,
            });
        } else {
            assert.strictEqual(description, undefined);
        }
    }

    function test_helpers(test_case) {
        // debugging tip: add a `console.log(test_case)` here
        test_common_narrow(test_case);
        test_add_icon_data(test_case);
        test_get_title(test_case);
        test_get_description(test_case);
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
    const is_followed = [{operator: "is", operand: "followed"}];
    const channels_public = [{operator: "channels", operand: "public"}];
    const channel_topic_terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
    ];
    const has_reaction_sender_me = [
        {operator: "has", operand: "reaction"},
        {operator: "sender", operand: "me"},
    ];
    // foo channel exists
    const channel_term = [{operator: "channel", operand: foo_stream_id.toString()}];
    const invalid_channel_id = new_stream_id();
    const invalid_channel = [{operator: "channel", operand: invalid_channel_id.toString()}];
    const invalid_channel_with_topic = [
        {operator: "channel", operand: invalid_channel_id.toString()},
        {operator: "topic", operand: "bar"},
    ];
    const public_sub_id = new_stream_id();
    make_private_sub("psub", public_sub_id);
    const private_channel_term = [{operator: "channel", operand: public_sub_id.toString()}];
    const web_public_sub_id = new_stream_id();
    make_web_public_sub("webPublicSub", web_public_sub_id); // capitalized just to try be tricky and robust.
    const web_public_channel = [{operator: "channel", operand: web_public_sub_id.toString()}];
    const archived_sub_id = new_stream_id();
    make_archived_sub("archivedSub", archived_sub_id);
    const archived_channel_term = [{operator: "channel", operand: archived_sub_id.toString()}];
    const dm = [{operator: "dm", operand: "joe@example.com"}];
    const dm_with = [
        {operator: "dm", operand: "joe@example.com"},
        {operator: "with", operand: "12"},
    ];
    const dm_with_self = [{operator: "dm", operand: "me@example.com"}];
    const dm_group = [{operator: "dm", operand: "joe@example.com,STEVE@foo.com"}];
    const dm_with_guest = [{operator: "dm", operand: "alice@example.com"}];
    const dm_with_muted_user = [{operator: "dm", operand: "jeff@foo.com"}];
    const dm_with_muted_guest_user = [{operator: "dm", operand: "annie@foo.com"}];
    const dm_group_including_guest = [
        {operator: "dm", operand: "alice@example.com,joe@example.com"},
    ];
    const dm_group_including_muted_user = [
        {operator: "dm", operand: "jeff@foo.com,joe@example.com"},
    ];
    const dm_group_including_muted_guest_user = [
        {operator: "dm", operand: "annie@foo.com,joe@example.com"},
    ];
    const dm_group_including_missing_person = [
        {operator: "dm", operand: "joe@example.com,STEVE@foo.com,sally@doesnotexist.com"},
    ];
    // not common narrows, but used for browser title updates
    const is_alerted = [{operator: "is", operand: "alerted"}];
    const is_unread = [{operator: "is", operand: "unread"}];
    const channel_topic_near = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "near", operand: "12"},
    ];
    const dm_near = [
        {operator: "dm", operand: "joe@example.com"},
        {operator: "near", operand: "12"},
    ];
    const channel_with = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "with", operand: "12"},
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
            zulip_icon: "star",
            title: "translated: Starred messages",
            redirect_url_with_search: "/#narrow/is/starred",
            description: "translated: Important messages, tasks, and other useful references.",
            link: "/help/star-a-message#view-your-starred-messages",
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
            zulip_icon: "user",
            title: "translated: Direct message feed",
            redirect_url_with_search: "/#narrow/is/dm",
        },
        {
            terms: is_mentioned,
            is_common_narrow: true,
            zulip_icon: "at-sign",
            title: "translated: Mentions",
            redirect_url_with_search: "/#narrow/is/mentioned",
            description: "translated: Messages where you are mentioned.",
            link: "/help/view-your-mentions",
        },
        {
            terms: is_resolved,
            is_common_narrow: true,
            icon: "check",
            title: "translated: Resolved topics",
            redirect_url_with_search: "/#narrow/topics/is/resolved",
        },
        {
            terms: is_followed,
            is_common_narrow: true,
            zulip_icon: "follow",
            title: "translated: Followed topics",
            redirect_url_with_search: "/#narrow/topics/is/followed",
            description: "translated: Messages in topics you follow.",
            link: "/help/follow-a-topic",
        },
        {
            terms: channel_topic_terms,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: `/#narrow/channel/${foo_stream_id}-Foo/topic/bar`,
        },
        {
            terms: invalid_channel_with_topic,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown channel",
            redirect_url_with_search: "#",
        },
        {
            terms: channels_public,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages in all public channels",
            redirect_url_with_search: "/#narrow/channels/public",
        },
        {
            terms: channel_term,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: `/#narrow/channel/${foo_stream_id}-Foo`,
        },
        {
            terms: invalid_channel,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown channel",
            redirect_url_with_search: "#",
        },
        {
            terms: private_channel_term,
            is_common_narrow: true,
            zulip_icon: "lock",
            title: "psub",
            redirect_url_with_search: `/#narrow/channel/${public_sub_id}-psub`,
        },
        {
            terms: web_public_channel,
            is_common_narrow: true,
            zulip_icon: "globe",
            title: "webPublicSub",
            redirect_url_with_search: `/#narrow/channel/${web_public_sub_id}-webPublicSub`,
        },
        {
            terms: archived_channel_term,
            is_common_narrow: true,
            zulip_icon: "archive",
            title: "archivedSub",
            redirect_url_with_search: `/#narrow/channel/${archived_sub_id}-archivedSub`,
        },
        {
            terms: dm,
            is_common_narrow: true,
            zulip_icon: "user",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search:
                "/#narrow/dm/" + joe.user_id + "-" + parseOneAddress(joe.email).local,
        },
        {
            terms: dm_group,
            is_common_narrow: true,
            zulip_icon: "user",
            title: properly_separated_names([joe.full_name, steve.full_name]),
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + steve.user_id + "-group",
        },
        {
            terms: dm_with_muted_user,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "translated: Muted user",
            redirect_url_with_search: "/#narrow/dm/" + jeff.user_id + "-" + jeff.full_name,
        },
        {
            terms: dm_with_muted_guest_user,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "translated: Muted user (guest)",
            redirect_url_with_search: "/#narrow/dm/" + annie.user_id + "-" + annie.full_name,
        },
        {
            terms: dm_with_guest,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "translated: alice (guest)",
            redirect_url_with_search:
                "/#narrow/dm/" + alice.user_id + "-" + parseOneAddress(alice.email).local,
        },
        {
            terms: dm_group_including_guest,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "joe and translated: alice (guest)",
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + alice.user_id + "-group",
        },
        {
            terms: dm_group_including_muted_user,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "joe and translated: Muted user",
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + jeff.user_id + "-group",
        },
        {
            terms: dm_group_including_muted_guest_user,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "joe and translated: Muted user (guest)",
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + annie.user_id + "-group",
        },
        {
            terms: dm_group_including_missing_person,
            is_common_narrow: true,
            zulip_icon: "user",
            title: properly_separated_names([
                joe.full_name,
                "sally@doesnotexist.com",
                steve.full_name,
            ]),
            redirect_url_with_search: "/#narrow/dm/undefined",
        },
        {
            terms: has_reaction_sender_me,
            is_common_narrow: true,
            zulip_icon: "smile",
            title: "translated: Reactions",
            redirect_url_with_search: "/#narrow/has/reaction/sender/me",
            description: "translated: Emoji reactions to your messages.",
            link: "/help/emoji-reactions",
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
            zulip_icon: "user",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search: "#",
        },
        {
            terms: channel_with,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "#",
        },
        {
            terms: dm_with,
            is_common_narrow: true,
            zulip_icon: "user",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search: "#",
        },
        {
            terms: dm_with_self,
            is_common_narrow: true,
            zulip_icon: "user",
            title: "translated: Messages with yourself",
            redirect_url_with_search: "/#narrow/dm/30-Me-Myself",
        },
    ];

    override(realm, "realm_enable_guest_user_indicator", true);

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
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "sender", operand: "me"},
    ];

    const redirect_url = "#";

    let filter = new Filter(complex_term);
    assert.equal(filter.generate_redirect_url(), redirect_url);
    assert.equal(filter.is_common_narrow(), false);

    const channel_topic_search_term = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "potato"},
    ];

    const channel_topic_search_term_test_case = {
        terms: channel_topic_search_term,
        title: undefined,
    };

    test_get_title(channel_topic_search_term_test_case);

    page_params.is_spectator = true;
    const channels_public_search_test_case_for_spectator = {
        terms: channels_public,
        title: "translated: Messages in all public channels that you can view",
    };
    test_get_title(channels_public_search_test_case_for_spectator);
    page_params.is_spectator = false;

    override(realm, "realm_enable_guest_user_indicator", false);
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
            zulip_icon: "user",
            title: properly_separated_names([alice.full_name]),
            redirect_url_with_search:
                "/#narrow/dm/" + alice.user_id + "-" + parseOneAddress(alice.email).local,
        },
        {
            terms: dm_group_including_guest,
            is_common_narrow: true,
            zulip_icon: "user",
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
        terms: [{operator: "channel", operand: foo_stream_id.toString()}],
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
    assert.ok(Filter.is_spectator_compatible([{operator: "is", operand: "resolved"}]));
    assert.ok(
        Filter.is_spectator_compatible([{operator: "is", operand: "resolved", negated: true}]),
    );
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

    const denmark_id = new_stream_id();
    make_sub("Denmark", denmark_id);
    assert.ok(
        Filter.is_spectator_compatible([{operator: "channel", operand: denmark_id.toString()}]),
    );
    assert.ok(
        Filter.is_spectator_compatible([
            {operator: "channel", operand: denmark_id.toString()},
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

run_test("excludes_muted_topics", () => {
    let filter = new Filter([{operator: "is", operand: "starred"}]);
    assert.ok(!filter.excludes_muted_topics());

    filter = new Filter([{operator: "is", operand: "muted"}]);
    assert.ok(!filter.excludes_muted_topics());

    filter = new Filter([{operator: "in", operand: "home", negated: true}]);
    assert.ok(!filter.excludes_muted_topics());

    filter = new Filter([{operator: "search", operand: "pizza"}]);
    assert.ok(!filter.excludes_muted_topics());

    filter = new Filter([
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "bar"},
    ]);
    assert.ok(!filter.excludes_muted_topics());

    filter = new Filter([{operator: "is", operand: "dm"}]);
    assert.ok(!filter.excludes_muted_topics());
});

run_test("equals", () => {
    let terms = [{operator: "channel", operand: foo_stream_id.toString()}];
    let filter = new Filter(terms);

    assert.ok(filter.equals(new Filter(terms)));
    assert.ok(!filter.equals(new Filter([])));
    assert.ok(!filter.equals(new Filter([{operand: "Bar", operator: "channel"}])));
    assert.ok(!filter.equals(new Filter([...terms, {operator: "topic", operand: "Bar"}])));

    terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "topic", operand: "Bar"},
    ];
    filter = new Filter(terms);
    assert.ok(
        filter.equals(
            new Filter([
                {operator: "topic", operand: "Bar"},
                {operator: "channel", operand: foo_stream_id.toString()},
            ]),
        ),
    );
    assert.ok(!filter.equals(new Filter([...terms, {operator: "near", operand: "10"}])));

    // Exclude `near` operator from comparison.
    assert.ok(filter.equals(new Filter([...terms, {operator: "near", operand: "10"}]), ["near"]));
    assert.ok(
        filter.equals(
            new Filter([
                {operator: "near", operand: "10"},
                {operator: "topic", operand: "Bar"},
                {operator: "channel", operand: foo_stream_id.toString()},
                {operator: "near", operand: "101"},
            ]),
            ["near"],
        ),
    );
});

run_test("adjusted_terms_if_moved", ({override}) => {
    override(current_user, "email", me.email);
    // should return null for non-stream messages containing no
    // `with` operator
    let raw_terms = [{operator: "channel", operand: foo_stream_id.toString()}];
    let message = {type: "private"};
    let result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.strictEqual(result, null);

    // should adjust terms to contain `dm` for non-stream messages
    // if it contains `with` operator
    message = {
        type: "private",
        id: 2,
        display_recipient: [
            {id: 3, email: "user3@zulip.com"},
            {id: me.user_id, email: me.email},
        ],
    };
    raw_terms = [
        {operator: "channel", operand: foo_stream_id.toString()},
        {operator: "with", operand: `${message.id}`},
    ];
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.deepEqual(result, [
        {operator: "dm", operand: "user3@zulip.com", negated: false},
        {operator: "with", operand: "2"},
    ]);

    message = {
        type: "private",
        id: 2,
        display_recipient: [{id: me.user_id, email: me.email}],
    };
    raw_terms = [
        {operator: "channel", operand: "Foo"},
        {operator: "with", operand: `${message.id}`},
    ];
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.deepEqual(result, [
        {operator: "dm", operand: me.email, negated: false},
        {operator: "with", operand: "2"},
    ]);

    // should return null if no terms are changed
    raw_terms = [{operator: "channel", operand: general_sub.stream_id.toString()}];
    message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        display_recipient: "general",
        topic: "discussion",
    };
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.strictEqual(result, null);

    // should adjust channel term to match message's display_recipient
    raw_terms = [{operator: "channel", operand: "999"}];
    message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        display_recipient: "general",
        topic: "discussion",
    };
    let expected = [{operator: "channel", operand: general_sub.stream_id.toString()}];
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.deepStrictEqual(result, expected);

    // should adjust topic term to match message's topic
    raw_terms = [{operator: "topic", operand: "random"}];
    message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        display_recipient: "general",
        topic: "discussion",
    };
    expected = [{operator: "topic", operand: "discussion"}];
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.deepStrictEqual(result, expected);

    // should adjust both channel and topic terms when both are different
    raw_terms = [
        {operator: "channel", operand: "999"},
        {operator: "topic", operand: "random"},
    ];
    message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        display_recipient: "general",
        topic: "discussion",
    };
    expected = [
        {operator: "channel", operand: general_sub.stream_id.toString()},
        {operator: "topic", operand: "discussion"},
    ];
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.deepStrictEqual(result, expected);

    // should not adjust terms that are not channel or topic
    raw_terms = [
        {operator: "channel", operand: "999"},
        {operator: "topic", operand: "random"},
        {operator: "sender", operand: "alice"},
    ];
    message = {
        type: "stream",
        stream_id: general_sub.stream_id,
        display_recipient: "general",
        topic: "discussion",
    };
    expected = [
        {operator: "channel", operand: general_sub.stream_id.toString()},
        {operator: "topic", operand: "discussion"},
        {operator: "sender", operand: "alice"},
    ];
    result = Filter.adjusted_terms_if_moved(raw_terms, message);
    assert.deepStrictEqual(result, expected);
});

run_test("can_newly_match_moved_messages", () => {
    // Matches stream
    let filter = new Filter([{operator: "channel", operand: "general"}]);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "test"), true);
    assert.deepEqual(filter.can_newly_match_moved_messages("General", "test"), true);
    assert.deepEqual(filter.can_newly_match_moved_messages("random-stream", "test"), false);

    // Matches topic
    filter = new Filter([{operator: "topic", operand: "Test topic"}]);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "Test topic"), true);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "test topic"), true);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "random topic"), false);

    // Matches common narrows
    filter = new Filter([{operator: "is", operand: "followed"}]);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "test"), true);

    filter = new Filter([{operator: "is", operand: "starred"}]);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "test"), false);

    filter = new Filter([
        {negated: true, operator: "channel", operand: general_sub.stream_id.toString()},
    ]);
    assert.deepEqual(filter.can_newly_match_moved_messages("something-else", "test"), true);

    filter = new Filter([{negated: true, operator: "is", operand: "followed"}]);
    assert.deepEqual(filter.can_newly_match_moved_messages("general", "test"), true);
});

run_test("get_stringified_narrow_for_server_query", () => {
    const filter = new Filter([
        {operator: "channel", operand: "1"},
        {operator: "topic", operand: "bar"},
    ]);
    const narrow = filter.get_stringified_narrow_for_server_query();
    assert.equal(
        narrow,
        '[{"negated":false,"operator":"channel","operand":1},{"negated":false,"operator":"topic","operand":"bar"}]',
    );
});

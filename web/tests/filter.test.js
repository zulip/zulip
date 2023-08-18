"use strict";

const {strict: assert} = require("assert");

const {parseOneAddress} = require("email-addresses");

const {mock_esm, with_overrides, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const blueslip = require("./lib/zblueslip");
const $ = require("./lib/zjquery");
const {page_params} = require("./lib/zpage_params");

const message_store = mock_esm("../src/message_store");

const resolved_topic = zrequire("../shared/src/resolved_topic");
const stream_data = zrequire("stream_data");
const people = zrequire("people");
const {Filter} = zrequire("../src/filter");

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

people.add_active_user(me);
people.add_active_user(joe);
people.add_active_user(steve);
people.initialize_current_user(me.user_id);

function assert_same_operators(result, terms) {
    // If negated flag is undefined, we explicitly
    // set it to false.
    terms = terms.map(({negated = false, operator, operand}) => ({negated, operator, operand}));
    assert.deepEqual(result, terms);
}

function get_predicate(operators) {
    operators = operators.map((op) => ({
        operator: op[0],
        operand: op[1],
    }));
    return new Filter(operators).predicate();
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
    let operators = [
        {operator: "stream", operand: "foo"},
        {operator: "stream", operand: "exclude_stream", negated: true},
        {operator: "topic", operand: "bar"},
    ];
    let filter = new Filter(operators);

    assert_same_operators(filter.operators(), operators);
    assert.deepEqual(filter.operands("stream"), ["foo"]);

    assert.ok(filter.has_operator("stream"));
    assert.ok(!filter.has_operator("search"));

    assert.ok(filter.has_operand("stream", "foo"));
    assert.ok(!filter.has_operand("stream", "exclude_stream"));
    assert.ok(!filter.has_operand("stream", "nada"));

    assert.ok(!filter.is_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "pizza"},
    ];
    filter = new Filter(operators);

    assert.ok(filter.is_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.can_bucket_by("stream"));
    assert.ok(filter.can_bucket_by("stream", "topic"));
    assert.ok(!filter.is_conversation_view());

    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "near", operand: 17},
    ];
    filter = new Filter(operators);

    assert.ok(!filter.is_search());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.can_bucket_by("stream"));
    assert.ok(filter.can_bucket_by("stream", "topic"));
    assert.ok(!filter.is_conversation_view());

    // If our only stream operator is negated, then for all intents and purposes,
    // we don't consider ourselves to have a stream operator, because we don't
    // want to have the stream in the tab bar or unsubscribe messaging, etc.
    operators = [{operator: "stream", operand: "exclude", negated: true}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("stream"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // Negated searches are just like positive searches for our purposes, since
    // the search logic happens on the backend and we need to have can_apply_locally()
    // be false, and we want "Search results" in the tab bar.
    operators = [{operator: "search", operand: "stop_word", negated: true}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.has_operator("search"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // Similar logic applies to negated "has" searches.
    operators = [{operator: "has", operand: "images", negated: true}];
    filter = new Filter(operators);
    assert.ok(filter.has_operator("has"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.can_apply_locally(true));
    assert.ok(!filter.includes_full_stream_history());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [{operator: "streams", operand: "public", negated: true}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("streams"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.has_negated_operand("streams", "public"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [{operator: "streams", operand: "public"}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.has_operator("streams"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.has_negated_operand("streams", "public"));
    assert.ok(!filter.can_apply_locally());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [{operator: "is", operand: "dm"}];
    filter = new Filter(operators);
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // "is:private" was renamed to "is:dm"
    operators = [{operator: "is", operand: "private"}];
    filter = new Filter(operators);
    assert.ok(filter.has_operand("is", "dm"));
    assert.ok(!filter.has_operand("is", "private"));

    operators = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [{operator: "is", operand: "starred"}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(!filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [{operator: "dm", operand: "joe@example.com"}];
    filter = new Filter(operators);
    assert.ok(filter.is_non_huddle_pm());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());

    operators = [{operator: "dm", operand: "joe@example.com,jack@example.com"}];
    filter = new Filter(operators);
    assert.ok(!filter.is_non_huddle_pm());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());

    // "pm-with" was renamed to "dm"
    operators = [{operator: "pm-with", operand: "joe@example.com"}];
    filter = new Filter(operators);
    assert.ok(filter.has_operator("dm"));
    assert.ok(!filter.has_operator("    pm-with"));

    operators = [{operator: "dm-including", operand: "joe@example.com"}];
    filter = new Filter(operators);
    assert.ok(!filter.is_non_huddle_pm());
    assert.ok(filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // "group-pm-with" was replaced with "dm-including"
    operators = [{operator: "group-pm-with", operand: "joe@example.com"}];
    filter = new Filter(operators);
    assert.ok(filter.has_operator("dm-including"));
    assert.ok(!filter.has_operator("group-pm-with"));

    operators = [{operator: "is", operand: "resolved"}];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    // Highly complex query to exercise
    // filter.supports_collapsing_recipients loop.
    operators = [
        {operator: "is", operand: "resolved", negated: true},
        {operator: "is", operand: "dm", negated: true},
        {operator: "stream", operand: "stream_name", negated: true},
        {operator: "streams", operand: "web-public", negated: true},
        {operator: "streams", operand: "public"},
        {operator: "topic", operand: "patience", negated: true},
        {operator: "in", operand: "all"},
    ];
    filter = new Filter(operators);
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(!filter.has_operator("search"));
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    // This next check verifies what is probably a bug; see the
    // comment in the can_apply_locally implementation.
    assert.ok(!filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(!filter.is_conversation_view());

    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(operators);

    assert.ok(!filter.is_search());
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.supports_collapsing_recipients());
    assert.ok(!filter.contains_only_private_messages());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
    assert.ok(filter.includes_full_stream_history());
    assert.ok(filter.can_apply_locally());
    assert.ok(!filter.is_personal_filter());
    assert.ok(filter.is_conversation_view());
});

function assert_not_mark_read_with_has_operands(additional_operators_to_test) {
    additional_operators_to_test = additional_operators_to_test || [];
    let has_operator = [{operator: "has", operand: "link"}];
    let filter = new Filter([...additional_operators_to_test, ...has_operator]);
    assert.ok(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "link", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...has_operator]);
    assert.ok(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "image"}];
    filter = new Filter([...additional_operators_to_test, ...has_operator]);
    assert.ok(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "image", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...has_operator]);
    assert.ok(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "attachment", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...has_operator]);
    assert.ok(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "attachment"}];
    filter = new Filter([...additional_operators_to_test, ...has_operator]);
    assert.ok(!filter.can_mark_messages_read());
}
function assert_not_mark_read_with_is_operands(additional_operators_to_test) {
    additional_operators_to_test = additional_operators_to_test || [];
    let is_operator = [{operator: "is", operand: "starred"}];
    let filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "starred", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "mentioned"}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "mentioned", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "alerted"}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "alerted", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "unread"}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "unread", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "resolved"}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    if (additional_operators_to_test.length === 0) {
        assert.ok(filter.can_mark_messages_read());
    } else {
        assert.ok(!filter.can_mark_messages_read());
    }

    is_operator = [{operator: "is", operand: "resolved", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...is_operator]);
    assert.ok(!filter.can_mark_messages_read());
}

function assert_not_mark_read_when_searching(additional_operators_to_test) {
    additional_operators_to_test = additional_operators_to_test || [];
    let search_op = [{operator: "search", operand: "keyword"}];
    let filter = new Filter([...additional_operators_to_test, ...search_op]);
    assert.ok(!filter.can_mark_messages_read());

    search_op = [{operator: "search", operand: "keyword", negated: true}];
    filter = new Filter([...additional_operators_to_test, ...search_op]);
    assert.ok(!filter.can_mark_messages_read());
}

test("can_mark_messages_read", () => {
    assert_not_mark_read_with_has_operands();
    assert_not_mark_read_with_is_operands();
    assert_not_mark_read_when_searching();

    const stream_operator = [{operator: "stream", operand: "foo"}];
    let filter = new Filter(stream_operator);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(stream_operator);
    assert_not_mark_read_with_is_operands(stream_operator);
    assert_not_mark_read_when_searching(stream_operator);

    const stream_negated_operator = [{operator: "stream", operand: "foo", negated: true}];
    filter = new Filter(stream_negated_operator);
    assert.ok(!filter.can_mark_messages_read());

    const stream_topic_operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(stream_topic_operators);
    assert.ok(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(stream_topic_operators);
    assert_not_mark_read_with_is_operands(stream_topic_operators);
    assert_not_mark_read_when_searching(stream_topic_operators);

    const stream_negated_topic_operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar", negated: true},
    ];
    filter = new Filter(stream_negated_topic_operators);
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
    let operators = [{operator: "is", operand: "any"}];
    let filter = new Filter(operators);
    assert.ok(filter.allow_use_first_unread_when_narrowing());

    operators = [{operator: "search", operand: "query to search"}];
    filter = new Filter(operators);
    assert.ok(!filter.allow_use_first_unread_when_narrowing());

    filter = new Filter();
    assert.ok(filter.can_mark_messages_read());
    assert.ok(filter.allow_use_first_unread_when_narrowing());

    // Side case
    operators = [{operator: "is", operand: "any"}];
    filter = new Filter(operators);
    assert.ok(!filter.can_mark_messages_read());
    assert.ok(filter.allow_use_first_unread_when_narrowing());
});

test("filter_with_new_params_topic", () => {
    const operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(operators);

    assert.ok(filter.has_topic("foo", "old topic"));
    assert.ok(!filter.has_topic("wrong", "old topic"));
    assert.ok(!filter.has_topic("foo", "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "topic",
        operand: "new topic",
    });

    assert.deepEqual(new_filter.operands("stream"), ["foo"]);
    assert.deepEqual(new_filter.operands("topic"), ["new topic"]);
});

test("filter_with_new_params_stream", () => {
    const operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(operators);

    assert.ok(filter.has_topic("foo", "old topic"));
    assert.ok(!filter.has_topic("wrong", "old topic"));
    assert.ok(!filter.has_topic("foo", "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "stream",
        operand: "new stream",
    });

    assert.deepEqual(new_filter.operands("stream"), ["new stream"]);
    assert.deepEqual(new_filter.operands("topic"), ["old topic"]);
});

test("new_style_operators", () => {
    const term = {
        operator: "stream",
        operand: "foo",
    };
    const operators = [term];
    const filter = new Filter(operators);

    assert.deepEqual(filter.operands("stream"), ["foo"]);
    assert.ok(filter.can_bucket_by("stream"));
});

test("public_operators", ({override}) => {
    stream_data.clear_subscriptions();
    let operators = [
        {operator: "stream", operand: "some_stream"},
        {operator: "in", operand: "all"},
        {operator: "topic", operand: "bar"},
    ];

    let filter = new Filter(operators);
    override(page_params, "narrow_stream", undefined);
    assert_same_operators(filter.public_operators(), operators);
    assert.ok(filter.can_bucket_by("stream"));

    operators = [{operator: "stream", operand: "default"}];
    filter = new Filter(operators);
    override(page_params, "narrow_stream", "default");
    assert_same_operators(filter.public_operators(), []);
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
    assert.equal(Filter.canonicalize_operator("Stream"), "stream");
    assert.equal(Filter.canonicalize_operator("Subject"), "topic");
    assert.equal(Filter.canonicalize_operator("FROM"), "sender");

    let term;
    term = Filter.canonicalize_term({operator: "Stream", operand: "Denmark"});
    assert.equal(term.operator, "stream");
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
        ["stream", "Foo"],
        ["topic", "Bar"],
    ]);

    assert.ok(predicate({type: "stream", stream_id, topic: "bar"}));
    assert.ok(!predicate({type: "stream", stream_id, topic: "whatever"}));
    // 9999999 doesn't exist, testing no match
    assert.ok(!predicate({type: "stream", stream_id: 9999999}));
    assert.ok(!predicate({type: "private"}));

    // For old streams that we are no longer subscribed to, we may not have
    // a sub, but these should still match by stream name.
    const old_sub = {
        name: "old-Stream",
        stream_id: 5,
        subscribed: false,
    };
    stream_data.add_sub(old_sub);
    predicate = get_predicate([
        ["stream", "old-Stream"],
        ["topic", "Bar"],
    ]);
    assert.ok(predicate({type: "stream", stream_id: 5, topic: "bar"}));
    // 99999 doesn't exist, testing no match
    assert.ok(!predicate({type: "stream", stream_id: 99999, topic: "whatever"}));

    predicate = get_predicate([["search", "emoji"]]);
    assert.ok(predicate({}));

    predicate = get_predicate([["topic", "Bar"]]);
    assert.ok(!predicate({type: "private"}));

    predicate = get_predicate([["is", "dm"]]);
    assert.ok(predicate({type: "private"}));
    assert.ok(!predicate({type: "stream"}));

    predicate = get_predicate([["streams", "public"]]);
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
    assert.ok(predicate({type: "stream", topic: resolved_topic_name}));
    assert.ok(!predicate({topic: resolved_topic_name}));
    assert.ok(!predicate({type: "stream", topic: "foo"}));

    const unknown_stream_id = 999;
    predicate = get_predicate([["in", "home"]]);
    assert.ok(!predicate({stream_id: unknown_stream_id, stream: "unknown"}));
    assert.ok(predicate({type: "private"}));

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
    assert.ok(predicate({type: "stream", id: 5, topic: "lunch"}));
    assert.ok(!predicate({type: "stream", id: 5, topic: "dinner"}));

    predicate = get_predicate([["sender", "Joe@example.com"]]);
    assert.ok(predicate({sender_id: joe.user_id}));
    assert.ok(!predicate({sender_email: steve.user_id}));

    predicate = get_predicate([["dm", "Joe@example.com"]]);
    assert.ok(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}],
        }),
    );
    assert.ok(
        !predicate({
            type: "private",
            display_recipient: [{id: steve.user_id}],
        }),
    );
    assert.ok(
        !predicate({
            type: "private",
            display_recipient: [{id: 999999}],
        }),
    );
    assert.ok(!predicate({type: "stream"}));

    predicate = get_predicate([["dm", "Joe@example.com,steve@foo.com"]]);
    assert.ok(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );

    // Make sure your own email is ignored
    predicate = get_predicate([["dm", "Joe@example.com,steve@foo.com,me@example.com"]]);
    assert.ok(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );

    predicate = get_predicate([["dm", "nobody@example.com"]]);
    assert.ok(
        !predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}],
        }),
    );

    predicate = get_predicate([["dm-including", "nobody@example.com"]]);
    assert.ok(
        !predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: me.user_id}],
        }),
    );

    predicate = get_predicate([["dm-including", "Joe@example.com"]]);
    assert.ok(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}, {id: me.user_id}],
        }),
    );
    assert.ok(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: me.user_id}],
        }),
    );
    assert.ok(
        !predicate({
            type: "private",
            display_recipient: [{id: steve.user_id}, {id: me.user_id}],
        }),
    );
    assert.ok(!predicate({type: "stream"}));

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

    narrow = [{operator: "stream", operand: "social", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert.ok(predicate({type: "stream", stream_id: 999999}));
    assert.ok(!predicate({type: "stream", stream_id: social_stream_id}));

    narrow = [{operator: "streams", operand: "public", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert.ok(predicate({}));
});

function test_mit_exceptions() {
    const foo_stream_id = 555;
    make_sub("Foo", foo_stream_id);
    let predicate = get_predicate([
        ["stream", "Foo"],
        ["topic", "personal"],
    ]);
    assert.ok(predicate({type: "stream", stream_id: foo_stream_id, topic: "personal"}));
    assert.ok(predicate({type: "stream", stream_id: foo_stream_id, topic: ""}));
    // 9999 doesn't correspond to any stream
    assert.ok(!predicate({type: "stream", stream_id: 9999}));
    assert.ok(!predicate({type: "stream", stream_id: foo_stream_id, topic: "whatever"}));
    assert.ok(!predicate({type: "private"}));

    predicate = get_predicate([
        ["stream", "Foo"],
        ["topic", "bar"],
    ]);
    assert.ok(predicate({type: "stream", stream_id: foo_stream_id, topic: "bar.d"}));

    // Try to get the MIT regex to explode for an empty stream.
    let terms = [
        {operator: "stream", operand: ""},
        {operator: "topic", operand: "bar"},
    ];
    predicate = new Filter(terms).predicate();
    assert.ok(!predicate({type: "stream", stream_id: foo_stream_id, topic: "bar"}));

    // Try to get the MIT regex to explode for an empty topic.
    terms = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: ""},
    ];
    predicate = new Filter(terms).predicate();
    assert.ok(!predicate({type: "stream", stream_id: foo_stream_id, topic: "bar"}));
}

test("mit_exceptions", ({override}) => {
    override(page_params, "realm_is_zephyr_mirror_realm", true);
    test_mit_exceptions();
});

test("predicate_edge_cases", () => {
    let predicate;
    // The code supports undefined as an operator to Filter, which results
    // in a predicate that accepts any message.
    predicate = new Filter().predicate();
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
        {operator: "stream", operand: "Off topic"},
        {operator: "topic", operand: "Mars"},
    ];
    const filter = new Filter(terms);
    filter.predicate();
    predicate = filter.predicate(); // get cached version
    assert.ok(predicate({type: "stream", stream_id, topic: "Mars"}));
});

test("parse", () => {
    let string;
    let operators;

    function _test() {
        const result = Filter.parse(string);
        assert_same_operators(result, operators);
    }

    string = "stream:Foo topic:Bar yo";
    operators = [
        {operator: "stream", operand: "Foo"},
        {operator: "topic", operand: "Bar"},
        {operator: "search", operand: "yo"},
    ];
    _test();

    string = "dm:leo+test@zulip.com";
    operators = [{operator: "dm", operand: "leo+test@zulip.com"}];
    _test();

    string = "sender:leo+test@zulip.com";
    operators = [{operator: "sender", operand: "leo+test@zulip.com"}];
    _test();

    string = "stream:With+Space";
    operators = [{operator: "stream", operand: "With Space"}];
    _test();

    string = 'stream:"with quoted space" topic:and separate';
    operators = [
        {operator: "stream", operand: "with quoted space"},
        {operator: "topic", operand: "and"},
        {operator: "search", operand: "separate"},
    ];
    _test();

    string = 'stream:"unclosed quote';
    operators = [{operator: "stream", operand: "unclosed quote"}];
    _test();

    string = 'stream:""';
    operators = [{operator: "stream", operand: ""}];
    _test();

    string = "https://www.google.com";
    operators = [{operator: "search", operand: "https://www.google.com"}];
    _test();

    string = "stream:foo -stream:exclude";
    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "stream", operand: "exclude", negated: true},
    ];
    _test();

    string = "text stream:foo more text";
    operators = [
        {operator: "search", operand: "text"},
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: "more text"},
    ];
    _test();

    string = "text streams:public more text";
    operators = [
        {operator: "search", operand: "text"},
        {operator: "streams", operand: "public"},
        {operator: "search", operand: "more text"},
    ];
    _test();

    string = "streams:public";
    operators = [{operator: "streams", operand: "public"}];
    _test();

    string = "-streams:public";
    operators = [{operator: "streams", operand: "public", negated: true}];
    _test();

    string = "stream:foo :emoji: are cool";
    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: ":emoji: are cool"},
    ];
    _test();

    string = ":stream: stream:foo :emoji: are cool";
    operators = [
        {operator: "search", operand: ":stream:"},
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: ":emoji: are cool"},
    ];
    _test();

    string = ":stream: stream:foo -:emoji: are cool";
    operators = [
        {operator: "search", operand: ":stream:"},
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: "-:emoji: are cool"},
    ];
    _test();

    string = "";
    operators = [];
    _test();

    string = 'stream: separated topic: "with space"';
    operators = [
        {operator: "stream", operand: "separated"},
        {operator: "topic", operand: "with space"},
    ];
    _test();
});

test("unparse", () => {
    let string;
    let operators;

    operators = [
        {operator: "stream", operand: "Foo"},
        {operator: "topic", operand: "Bar", negated: true},
        {operator: "search", operand: "yo"},
    ];
    string = "stream:Foo -topic:Bar yo";
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [
        {operator: "streams", operand: "public"},
        {operator: "search", operand: "text"},
    ];

    string = "streams:public text";
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [{operator: "streams", operand: "public"}];
    string = "streams:public";
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [{operator: "streams", operand: "public", negated: true}];
    string = "-streams:public";
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [{operator: "id", operand: 50}];
    string = "id:50";
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [{operator: "near", operand: 150}];
    string = "near:150";
    assert.deepEqual(Filter.unparse(operators), string);

    operators = [{operator: "", operand: ""}];
    string = "";
    assert.deepEqual(Filter.unparse(operators), string);
});

test("describe", ({mock_template}) => {
    let narrow;
    let string;
    mock_template("search_description.hbs", true, (_data, html) => html);

    narrow = [{operator: "streams", operand: "public"}];
    string = "streams public";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [{operator: "streams", operand: "public", negated: true}];
    string = "exclude streams public";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "is", operand: "starred"},
    ];
    string = "stream devel, starred messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "stream", operand: "river"},
        {operator: "is", operand: "unread"},
    ];
    string = "stream river, unread messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "JS"},
    ];
    string = "stream devel > JS";
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
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "JS", negated: true},
    ];
    string = "stream devel, exclude topic JS";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "is", operand: "dm"},
        {operator: "search", operand: "lunch", negated: true},
    ];
    string = "direct messages, exclude lunch";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "is", operand: "starred", negated: true},
    ];
    string = "stream devel, exclude starred messages";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "has", operand: "image", negated: true},
    ];
    string = "stream devel, exclude messages with one or more image";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "has", operand: "abc", negated: true},
        {operator: "stream", operand: "devel"},
    ];
    string = "invalid abc operand for has operator, stream devel";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [
        {operator: "has", operand: "image", negated: true},
        {operator: "stream", operand: "devel"},
    ];
    string = "exclude messages with one or more image, stream devel";
    assert.equal(Filter.search_description_as_html(narrow), string);

    narrow = [];
    string = "all messages";
    assert.equal(Filter.search_description_as_html(narrow), string);
});

test("can_bucket_by", () => {
    let terms = [{operator: "stream", operand: "My stream"}];
    let filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), true);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [
        // try a non-orthodox ordering
        {operator: "topic", operand: "My topic"},
        {operator: "stream", operand: "My stream"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), true);
    assert.equal(filter.can_bucket_by("stream", "topic"), true);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [
        {operator: "stream", operand: "My stream", negated: true},
        {operator: "topic", operand: "My topic"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), false);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [{operator: "dm", operand: "foo@example.com", negated: true}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), false);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("dm"), false);

    terms = [{operator: "dm", operand: "foo@example.com,bar@example.com"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), false);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
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
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("stream"), false);
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

    assert_term_type(term("streams", "public"), "streams-public");
    assert_term_type(term("stream", "whatever"), "stream");
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

    assert_term_sort(["topic", "stream", "sender"], ["stream", "topic", "sender"]);

    assert_term_sort(
        ["has-link", "near", "is-unread", "dm"],
        ["dm", "near", "is-unread", "has-link"],
    );

    assert_term_sort(["bogus", "stream", "topic"], ["stream", "topic", "bogus"]);
    assert_term_sort(["stream", "topic", "stream"], ["stream", "stream", "topic"]);

    assert_term_sort(["search", "streams-public"], ["streams-public", "search"]);

    const terms = [
        {operator: "topic", operand: "lunch"},
        {operator: "sender", operand: "steve@foo.com"},
        {operator: "stream", operand: "Verona"},
    ];
    let filter = new Filter(terms);
    const term_types = filter.sorted_term_types();

    assert.deepEqual(term_types, ["stream", "topic", "sender"]);

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
    assert.deepEqual(built_terms, ["stream", "topic", "sender"]);
    assert.ok(filter._build_sorted_term_types_called);

    // cached trial
    filter._build_sorted_term_types_called = false;
    const cached_terms = filter.sorted_term_types();
    assert.deepEqual(cached_terms, ["stream", "topic", "sender"]);
    assert.ok(!filter._build_sorted_term_types_called);
});

test("first_valid_id_from", ({override}) => {
    const terms = [{operator: "is", operand: "alerted"}];

    const filter = new Filter(terms);

    const messages = {
        5: {id: 5, alerted: true},
        10: {id: 10},
        20: {id: 20, alerted: true},
        30: {id: 30, type: "stream"},
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
        {operator: "stream", operand: "steve@foo.com"}, // try to be tricky
    ];
    const filter = new Filter(terms);
    filter.update_email(steve.user_id, "showell@foo.com");
    assert.deepEqual(filter.operands("dm"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("sender"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("stream"), ["steve@foo.com"]);
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
        return names.join(", ");
    }

    function test_redirect_url_with_search(test_case) {
        test_case.operator.push({operator: "search", operand: "fizzbuzz"});
        const filter = new Filter(test_case.operator);
        assert.equal(filter.generate_redirect_url(), test_case.redirect_url_with_search);
    }

    function test_common_narrow(test_case) {
        const filter = new Filter(test_case.operator);
        assert.equal(filter.is_common_narrow(), test_case.is_common_narrow);
    }

    function test_add_icon_data(test_case) {
        const filter = new Filter(test_case.operator);
        const context = {};
        filter.add_icon_data(context);
        assert.equal(context.icon, test_case.icon);
        assert.equal(context.zulip_icon, test_case.zulip_icon);
    }

    function test_get_title(test_case) {
        const filter = new Filter(test_case.operator);
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
    const in_home = [{operator: "in", operand: "home"}];
    const in_all = [{operator: "in", operand: "all"}];
    const is_starred = [{operator: "is", operand: "starred"}];
    const is_dm = [{operator: "is", operand: "dm"}];
    const is_mentioned = [{operator: "is", operand: "mentioned"}];
    const is_resolved = [{operator: "is", operand: "resolved"}];
    const streams_public = [{operator: "streams", operand: "public"}];
    const stream_topic_operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    // foo stream exists
    const stream_operator = [{operator: "stream", operand: "foo"}];
    make_private_sub("psub", "22");
    const private_stream_operator = [{operator: "stream", operand: "psub"}];
    make_web_public_sub("webPublicSub", "12"); // capitalized just to try be tricky and robust.
    const web_public_stream_operator = [{operator: "stream", operand: "webPublicSub"}];
    const non_existent_stream = [{operator: "stream", operand: "Elephant"}];
    const non_existent_stream_topic = [
        {operator: "stream", operand: "Elephant"},
        {operator: "topic", operand: "pink"},
    ];
    const dm = [{operator: "dm", operand: "joe@example.com"}];
    const dm_group = [{operator: "dm", operand: "joe@example.com,STEVE@foo.com"}];
    const dm_group_including_missing_person = [
        {operator: "dm", operand: "joe@example.com,STEVE@foo.com,sally@doesnotexist.com"},
    ];
    // not common narrows, but used for browser title updates
    const is_alerted = [{operator: "is", operand: "alerted"}];
    const is_unread = [{operator: "is", operand: "unread"}];
    const stream_topic_near = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "near", operand: "12"},
    ];
    const dm_near = [
        {operator: "dm", operand: "joe@example.com"},
        {operator: "near", operand: "12"},
    ];

    const test_cases = [
        {
            operator: sender,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages sent by " + joe.full_name,
            redirect_url_with_search: "/#narrow/sender/" + joe.user_id + "-joe",
        },
        {
            operator: is_starred,
            is_common_narrow: true,
            icon: "star",
            title: "translated: Starred messages",
            redirect_url_with_search: "/#narrow/is/starred",
        },
        {
            operator: in_home,
            is_common_narrow: true,
            icon: "home",
            title: "translated: All messages",
            redirect_url_with_search: "#",
        },
        {
            operator: in_all,
            is_common_narrow: true,
            icon: "home",
            title: "translated: All messages including muted streams",
            redirect_url_with_search: "#",
        },
        {
            operator: is_dm,
            is_common_narrow: true,
            icon: "envelope",
            title: "translated: Direct messages",
            redirect_url_with_search: "/#narrow/is/dm",
        },
        {
            operator: is_mentioned,
            is_common_narrow: true,
            icon: "at",
            title: "translated: Mentions",
            redirect_url_with_search: "/#narrow/is/mentioned",
        },
        {
            operator: is_resolved,
            is_common_narrow: true,
            icon: "check",
            title: "translated: Topics marked as resolved",
            redirect_url_with_search: "/#narrow/topics/is/resolved",
        },
        {
            operator: stream_topic_operators,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "/#narrow/stream/43-Foo/topic/bar",
        },
        {
            operator: streams_public,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Messages in all public streams",
            redirect_url_with_search: "/#narrow/streams/public",
        },
        {
            operator: stream_operator,
            is_common_narrow: true,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "/#narrow/stream/43-Foo",
        },
        {
            operator: non_existent_stream,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown stream #Elephant",
            redirect_url_with_search: "#",
        },
        {
            operator: non_existent_stream_topic,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown stream #Elephant",
            redirect_url_with_search: "#",
        },
        {
            operator: private_stream_operator,
            is_common_narrow: true,
            zulip_icon: "lock",
            title: "psub",
            redirect_url_with_search: "/#narrow/stream/22-psub",
        },
        {
            operator: web_public_stream_operator,
            is_common_narrow: true,
            zulip_icon: "globe",
            title: "webPublicSub",
            redirect_url_with_search: "/#narrow/stream/12-webPublicSub",
        },
        {
            operator: dm,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search:
                "/#narrow/dm/" + joe.user_id + "-" + parseOneAddress(joe.email).local,
        },
        {
            operator: dm_group,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([joe.full_name, steve.full_name]),
            redirect_url_with_search: "/#narrow/dm/" + joe.user_id + "," + steve.user_id + "-group",
        },
        {
            operator: dm_group_including_missing_person,
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
            operator: is_alerted,
            is_common_narrow: false,
            icon: undefined,
            title: "translated: Alerted messages",
            redirect_url_with_search: "#",
        },
        {
            operator: is_unread,
            is_common_narrow: false,
            icon: undefined,
            title: "translated: Unread messages",
            redirect_url_with_search: "#",
        },
        {
            operator: stream_topic_near,
            is_common_narrow: false,
            zulip_icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "#",
        },
        {
            operator: dm_near,
            is_common_narrow: false,
            icon: "envelope",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search: "#",
        },
    ];

    for (const test_case of test_cases) {
        test_helpers(test_case);
    }

    // TODO: these may be removed, based on design decisions
    const sender_me = [{operator: "sender", operand: "me"}];
    const sender_joe = [{operator: "sender", operand: joe.email}];

    const redirect_edge_cases = [
        {
            operator: sender_me,
            redirect_url_with_search: "/#narrow/sender/" + me.user_id + "-Me-Myself",
            is_common_narrow: true,
        },
        {
            operator: sender_joe,
            redirect_url_with_search: "/#narrow/sender/" + joe.user_id + "-joe",
            is_common_narrow: true,
        },
    ];

    for (const test_case of redirect_edge_cases) {
        test_redirect_url_with_search(test_case);
    }

    // TODO: test every single one of the "ALL" redirects from the navbar behaviour table

    // incomplete and weak test cases just to restore coverage of filter.js
    const complex_operator = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "sender", operand: "me"},
    ];

    const complex_operators_test_case = {
        operator: complex_operator,
        redirect_url: "#",
    };

    let filter = new Filter(complex_operators_test_case.operator);
    assert.equal(filter.generate_redirect_url(), complex_operators_test_case.redirect_url);
    assert.equal(filter.is_common_narrow(), false);

    const stream_topic_search_operator = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "potato"},
    ];

    const stream_topic_search_operator_test_case = {
        operator: stream_topic_search_operator,
        title: undefined,
    };

    test_get_title(stream_topic_search_operator_test_case);

    // this is actually wrong, but the code is currently not robust enough to throw an error here
    // also, used as an example of triggering last return statement.
    const default_redirect = {
        operator: [{operator: "stream", operand: "foo"}],
        redirect_url: "#",
    };

    filter = new Filter(default_redirect.operator);
    assert.equal(filter.generate_redirect_url(), default_redirect.redirect_url);
});

test("error_cases", () => {
    // This test just gives us 100% line coverage on defensive code that
    // should not be reached unless we break other code.

    const predicate = get_predicate([["dm", "Joe@example.com"]]);
    blueslip.expect("error", "Empty recipient list in message");
    assert.ok(!predicate({type: "private", display_recipient: []}));
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
    assert.ok(Filter.is_spectator_compatible([{operator: "stream", operand: "Denmark"}]));
    assert.ok(
        Filter.is_spectator_compatible([
            {operator: "stream", operand: "Denmark"},
            {operator: "topic", operand: "logic"},
        ]),
    );
    assert.ok(!Filter.is_spectator_compatible([{operator: "is", operand: "starred"}]));
    assert.ok(!Filter.is_spectator_compatible([{operator: "is", operand: "dm"}]));
    assert.ok(Filter.is_spectator_compatible([{operator: "streams", operand: "public"}]));

    // Malformed input not allowed
    assert.ok(!Filter.is_spectator_compatible([{operator: "has"}]));

    // "is:private" was renamed to "is:dm"
    assert.ok(!Filter.is_spectator_compatible([{operator: "is", operand: "private"}]));
    // "pm-with" was renamed to "dm"
    assert.ok(
        !Filter.is_spectator_compatible([{operator: "pm-with", operand: "hamlet@zulip.com"}]),
    );
    // "group-pm-with:" was replaced with "dm-including:"
    assert.ok(
        !Filter.is_spectator_compatible([{operator: "group-pm-with", operand: "hamlet@zulip.com"}]),
    );
});

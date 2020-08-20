"use strict";

zrequire("unread");
zrequire("stream_data");
const people = zrequire("people");
global.stub_out_jquery();
set_global("$", global.make_zjquery());
zrequire("message_util", "js/message_util");
zrequire("Filter", "js/filter");

set_global("message_store", {});
set_global("page_params", {});

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
    terms = terms.map((term) => {
        // If negated flag is undefined, we explicitly
        // set it to false.
        let negated = term.negated;
        if (!negated) {
            negated = false;
        }
        return {
            negated,
            operator: term.operator,
            operand: term.operand,
        };
    });
    assert.deepEqual(result, terms);
}

run_test("basics", () => {
    let operators = [
        {operator: "stream", operand: "foo"},
        {operator: "stream", operand: "exclude_stream", negated: true},
        {operator: "topic", operand: "bar"},
    ];
    let filter = new Filter(operators);

    assert_same_operators(filter.operators(), operators);
    assert.deepEqual(filter.operands("stream"), ["foo"]);

    assert(filter.has_operator("stream"));
    assert(!filter.has_operator("search"));

    assert(filter.has_operand("stream", "foo"));
    assert(!filter.has_operand("stream", "exclude_stream"));
    assert(!filter.has_operand("stream", "nada"));

    assert(!filter.is_search());
    assert(!filter.can_mark_messages_read());
    assert(!filter.contains_only_private_messages());
    assert(!filter.allow_use_first_unread_when_narrowing());
    assert(filter.includes_full_stream_history());
    assert(filter.can_apply_locally());
    assert(!filter.is_personal_filter());

    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
        {operator: "search", operand: "pizza"},
    ];
    filter = new Filter(operators);

    assert(filter.is_search());
    assert(!filter.can_mark_messages_read());
    assert(!filter.contains_only_private_messages());
    assert(!filter.allow_use_first_unread_when_narrowing());
    assert(!filter.can_apply_locally());
    assert(!filter.is_personal_filter());
    assert(filter.can_bucket_by("stream"));
    assert(filter.can_bucket_by("stream", "topic"));

    // If our only stream operator is negated, then for all intents and purposes,
    // we don't consider ourselves to have a stream operator, because we don't
    // want to have the stream in the tab bar or unsubscribe messaging, etc.
    operators = [{operator: "stream", operand: "exclude", negated: true}];
    filter = new Filter(operators);
    assert(!filter.contains_only_private_messages());
    assert(!filter.has_operator("stream"));
    assert(!filter.can_mark_messages_read());
    assert(!filter.is_personal_filter());

    // Negated searches are just like positive searches for our purposes, since
    // the search logic happens on the back end and we need to have can_apply_locally()
    // be false, and we want "Search results" in the tab bar.
    operators = [{operator: "search", operand: "stop_word", negated: true}];
    filter = new Filter(operators);
    assert(!filter.contains_only_private_messages());
    assert(filter.has_operator("search"));
    assert(!filter.can_apply_locally());
    assert(!filter.can_mark_messages_read());
    assert(!filter.is_personal_filter());

    // Similar logic applies to negated "has" searches.
    operators = [{operator: "has", operand: "images", negated: true}];
    filter = new Filter(operators);
    assert(filter.has_operator("has"));
    assert(filter.can_apply_locally());
    assert(!filter.can_apply_locally(true));
    assert(!filter.includes_full_stream_history());
    assert(!filter.can_mark_messages_read());
    assert(!filter.is_personal_filter());

    operators = [{operator: "streams", operand: "public", negated: true}];
    filter = new Filter(operators);
    assert(!filter.contains_only_private_messages());
    assert(!filter.has_operator("streams"));
    assert(!filter.can_mark_messages_read());
    assert(filter.has_negated_operand("streams", "public"));
    assert(!filter.can_apply_locally());
    assert(!filter.is_personal_filter());

    operators = [{operator: "streams", operand: "public"}];
    filter = new Filter(operators);
    assert(!filter.contains_only_private_messages());
    assert(filter.has_operator("streams"));
    assert(!filter.can_mark_messages_read());
    assert(!filter.has_negated_operand("streams", "public"));
    assert(!filter.can_apply_locally());
    assert(filter.includes_full_stream_history());
    assert(!filter.is_personal_filter());

    operators = [{operator: "is", operand: "private"}];
    filter = new Filter(operators);
    assert(filter.contains_only_private_messages());
    assert(filter.can_mark_messages_read());
    assert(!filter.has_operator("search"));
    assert(filter.can_apply_locally());
    assert(!filter.is_personal_filter());

    operators = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(operators);
    assert(!filter.contains_only_private_messages());
    assert(filter.can_mark_messages_read());
    assert(!filter.has_operator("search"));
    assert(filter.can_apply_locally());
    assert(filter.is_personal_filter());

    operators = [{operator: "is", operand: "starred"}];
    filter = new Filter(operators);
    assert(!filter.contains_only_private_messages());
    assert(!filter.can_mark_messages_read());
    assert(!filter.has_operator("search"));
    assert(filter.can_apply_locally());
    assert(filter.is_personal_filter());

    operators = [{operator: "pm-with", operand: "joe@example.com"}];
    filter = new Filter(operators);
    assert(filter.contains_only_private_messages());
    assert(!filter.has_operator("search"));
    assert(filter.can_apply_locally());
    assert(!filter.is_personal_filter());

    operators = [{operator: "group-pm-with", operand: "joe@example.com"}];
    filter = new Filter(operators);
    assert(filter.contains_only_private_messages());
    assert(!filter.has_operator("search"));
    assert(filter.can_apply_locally());
});

function assert_not_mark_read_with_has_operands(additional_operators_to_test) {
    additional_operators_to_test = additional_operators_to_test || [];
    let has_operator = [{operator: "has", operand: "link"}];
    let filter = new Filter(additional_operators_to_test.concat(has_operator));
    assert(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "link", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(has_operator));
    assert(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "image"}];
    filter = new Filter(additional_operators_to_test.concat(has_operator));
    assert(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "image", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(has_operator));
    assert(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "attachment", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(has_operator));
    assert(!filter.can_mark_messages_read());

    has_operator = [{operator: "has", operand: "attachment"}];
    filter = new Filter(additional_operators_to_test.concat(has_operator));
    assert(!filter.can_mark_messages_read());
}
function assert_not_mark_read_with_is_operands(additional_operators_to_test) {
    additional_operators_to_test = additional_operators_to_test || [];
    let is_operator = [{operator: "is", operand: "starred"}];
    let filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "starred", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    if (additional_operators_to_test.length === 0) {
        assert(filter.can_mark_messages_read());
    } else {
        assert(!filter.can_mark_messages_read());
    }

    is_operator = [{operator: "is", operand: "mentioned", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "alerted"}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "alerted", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "unread"}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());

    is_operator = [{operator: "is", operand: "unread", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(is_operator));
    assert(!filter.can_mark_messages_read());
}

function assert_not_mark_read_when_searching(additional_operators_to_test) {
    additional_operators_to_test = additional_operators_to_test || [];
    let search_op = [{operator: "search", operand: "keyword"}];
    let filter = new Filter(additional_operators_to_test.concat(search_op));
    assert(!filter.can_mark_messages_read());

    search_op = [{operator: "search", operand: "keyword", negated: true}];
    filter = new Filter(additional_operators_to_test.concat(search_op));
    assert(!filter.can_mark_messages_read());
}

run_test("can_mark_messages_read", () => {
    assert_not_mark_read_with_has_operands();
    assert_not_mark_read_with_is_operands();
    assert_not_mark_read_when_searching();

    const stream_operator = [{operator: "stream", operand: "foo"}];
    let filter = new Filter(stream_operator);
    assert(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(stream_operator);
    assert_not_mark_read_with_is_operands(stream_operator);
    assert_not_mark_read_when_searching(stream_operator);

    const stream_negated_operator = [{operator: "stream", operand: "foo", negated: true}];
    filter = new Filter(stream_negated_operator);
    assert(!filter.can_mark_messages_read());

    const stream_topic_operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar"},
    ];
    filter = new Filter(stream_topic_operators);
    assert(filter.can_mark_messages_read());
    assert_not_mark_read_with_has_operands(stream_topic_operators);
    assert_not_mark_read_with_is_operands(stream_topic_operators);
    assert_not_mark_read_when_searching(stream_topic_operators);

    const stream_negated_topic_operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "bar", negated: true},
    ];
    filter = new Filter(stream_negated_topic_operators);
    assert(!filter.can_mark_messages_read());

    const pm_with = [{operator: "pm-with", operand: "joe@example.com,"}];

    const pm_with_negated = [{operator: "pm-with", operand: "joe@example.com,", negated: true}];

    const group_pm = [{operator: "pm-with", operand: "joe@example.com,STEVE@foo.com"}];
    filter = new Filter(pm_with);
    assert(filter.can_mark_messages_read());
    filter = new Filter(pm_with_negated);
    assert(!filter.can_mark_messages_read());
    filter = new Filter(group_pm);
    assert(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(group_pm);
    assert_not_mark_read_with_is_operands(pm_with);
    assert_not_mark_read_with_has_operands(group_pm);
    assert_not_mark_read_with_has_operands(pm_with);
    assert_not_mark_read_when_searching(group_pm);
    assert_not_mark_read_when_searching(pm_with);

    const is_private = [{operator: "is", operand: "private"}];
    filter = new Filter(is_private);
    assert(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(is_private);
    assert_not_mark_read_with_has_operands(is_private);
    assert_not_mark_read_when_searching(is_private);

    const in_all = [{operator: "in", operand: "all"}];
    filter = new Filter(in_all);
    assert(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(in_all);
    assert_not_mark_read_with_has_operands(in_all);
    assert_not_mark_read_when_searching(in_all);

    const in_home = [{operator: "in", operand: "home"}];
    const in_home_negated = [{operator: "in", operand: "home", negated: true}];
    filter = new Filter(in_home);
    assert(filter.can_mark_messages_read());
    assert_not_mark_read_with_is_operands(in_home);
    assert_not_mark_read_with_has_operands(in_home);
    assert_not_mark_read_when_searching(in_home);
    filter = new Filter(in_home_negated);
    assert(!filter.can_mark_messages_read());

    // Do not mark messages as read when in an unsupported 'in:*' filter.
    const in_random = [{operator: "in", operand: "xxxxxxxxx"}];
    const in_random_negated = [{operator: "in", operand: "xxxxxxxxx", negated: true}];
    filter = new Filter(in_random);
    assert(!filter.can_mark_messages_read());
    filter = new Filter(in_random_negated);
    assert(!filter.can_mark_messages_read());

    // test caching of term types
    // init and stub
    filter = new Filter(pm_with);
    filter.stub = filter.calc_can_mark_messages_read;
    filter.calc_can_mark_messages_read = function () {
        this.calc_can_mark_messages_read_called = true;
        return this.stub();
    };

    // uncached trial
    filter.calc_can_mark_messages_read_called = false;
    assert(filter.can_mark_messages_read());
    assert(filter.calc_can_mark_messages_read_called);

    // cached trial
    filter.calc_can_mark_messages_read_called = false;
    assert(filter.can_mark_messages_read());
    assert(!filter.calc_can_mark_messages_read_called);
});

run_test("show_first_unread", () => {
    let operators = [{operator: "is", operand: "any"}];
    let filter = new Filter(operators);
    assert(filter.allow_use_first_unread_when_narrowing());

    operators = [{operator: "search", operand: "query to search"}];
    filter = new Filter(operators);
    assert(!filter.allow_use_first_unread_when_narrowing());

    filter = new Filter();
    filter.can_mark_messages_read = () => true;
    assert(filter.allow_use_first_unread_when_narrowing());

    // Side case
    operators = [{operator: "is", operand: "any"}];
    filter = new Filter(operators);
    filter.can_mark_messages_read = () => false;
    assert(filter.allow_use_first_unread_when_narrowing());
});
run_test("filter_with_new_params_topic", () => {
    const operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(operators);

    assert(filter.has_topic("foo", "old topic"));
    assert(!filter.has_topic("wrong", "old topic"));
    assert(!filter.has_topic("foo", "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "topic",
        operand: "new topic",
    });

    assert.deepEqual(new_filter.operands("stream"), ["foo"]);
    assert.deepEqual(new_filter.operands("topic"), ["new topic"]);
});

run_test("filter_with_new_params_stream", () => {
    const operators = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: "old topic"},
    ];
    const filter = new Filter(operators);

    assert(filter.has_topic("foo", "old topic"));
    assert(!filter.has_topic("wrong", "old topic"));
    assert(!filter.has_topic("foo", "wrong"));

    const new_filter = filter.filter_with_new_params({
        operator: "stream",
        operand: "new stream",
    });

    assert.deepEqual(new_filter.operands("stream"), ["new stream"]);
    assert.deepEqual(new_filter.operands("topic"), ["old topic"]);
});

run_test("new_style_operators", () => {
    const term = {
        operator: "stream",
        operand: "foo",
    };
    const operators = [term];
    const filter = new Filter(operators);

    assert.deepEqual(filter.operands("stream"), ["foo"]);
    assert(filter.can_bucket_by("stream"));
});

run_test("public_operators", () => {
    let operators = [
        {operator: "stream", operand: "foo"},
        {operator: "in", operand: "all"},
        {operator: "topic", operand: "bar"},
    ];

    let filter = new Filter(operators);
    assert_same_operators(filter.public_operators(), operators);
    assert(filter.can_bucket_by("stream"));

    global.page_params.narrow_stream = "default";
    operators = [{operator: "stream", operand: "default"}];
    filter = new Filter(operators);
    assert_same_operators(filter.public_operators(), []);
});

run_test("redundancies", () => {
    let terms;
    let filter;

    terms = [
        {operator: "pm-with", operand: "joe@example.com,"},
        {operator: "is", operand: "private"},
    ];
    filter = new Filter(terms);
    assert(filter.can_bucket_by("pm-with"));

    terms = [
        {operator: "pm-with", operand: "joe@example.com,", negated: true},
        {operator: "is", operand: "private"},
    ];
    filter = new Filter(terms);
    assert(filter.can_bucket_by("is-private", "not-pm-with"));
});

run_test("canonicalization", () => {
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

    term = Filter.canonicalize_term({operator: "pm-with", operand: "me"});
    assert.equal(term.operator, "pm-with");
    assert.equal(term.operand, "me@example.com");

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
    global.stream_data.add_sub(sub);
}

run_test("predicate_basics", () => {
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

    assert(predicate({type: "stream", stream_id, topic: "bar"}));
    assert(!predicate({type: "stream", stream_id, topic: "whatever"}));
    assert(!predicate({type: "stream", stream_id: 9999999}));
    assert(!predicate({type: "private"}));

    // For old streams that we are no longer subscribed to, we may not have
    // a sub, but these should still match by stream name.
    predicate = get_predicate([
        ["stream", "old-Stream"],
        ["topic", "Bar"],
    ]);
    assert(predicate({type: "stream", stream: "Old-stream", topic: "bar"}));
    assert(!predicate({type: "stream", stream: "no-match", topic: "whatever"}));

    predicate = get_predicate([["search", "emoji"]]);
    assert(predicate({}));

    predicate = get_predicate([["topic", "Bar"]]);
    assert(!predicate({type: "private"}));

    predicate = get_predicate([["is", "private"]]);
    assert(predicate({type: "private"}));
    assert(!predicate({type: "stream"}));

    predicate = get_predicate([["streams", "public"]]);
    assert(predicate({}));

    predicate = get_predicate([["is", "starred"]]);
    assert(predicate({starred: true}));
    assert(!predicate({starred: false}));

    predicate = get_predicate([["is", "unread"]]);
    assert(predicate({unread: true}));
    assert(!predicate({unread: false}));

    predicate = get_predicate([["is", "alerted"]]);
    assert(predicate({alerted: true}));
    assert(!predicate({alerted: false}));
    assert(!predicate({}));

    predicate = get_predicate([["is", "mentioned"]]);
    assert(predicate({mentioned: true}));
    assert(!predicate({mentioned: false}));

    predicate = get_predicate([["in", "all"]]);
    assert(predicate({}));

    const unknown_stream_id = 999;
    predicate = get_predicate([["in", "home"]]);
    assert(!predicate({stream_id: unknown_stream_id, stream: "unknown"}));
    assert(predicate({type: "private"}));
    global.page_params.narrow_stream = "kiosk";
    assert(predicate({stream: "kiosk"}));

    predicate = get_predicate([["near", 5]]);
    assert(predicate({}));

    predicate = get_predicate([["id", 5]]);
    assert(predicate({id: 5}));
    assert(!predicate({id: 6}));

    predicate = get_predicate([
        ["id", 5],
        ["topic", "lunch"],
    ]);
    assert(predicate({type: "stream", id: 5, topic: "lunch"}));
    assert(!predicate({type: "stream", id: 5, topic: "dinner"}));

    predicate = get_predicate([["sender", "Joe@example.com"]]);
    assert(predicate({sender_id: joe.user_id}));
    assert(!predicate({sender_email: steve.user_id}));

    predicate = get_predicate([["pm-with", "Joe@example.com"]]);
    assert(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}],
        }),
    );
    assert(
        !predicate({
            type: "private",
            display_recipient: [{id: steve.user_id}],
        }),
    );
    assert(
        !predicate({
            type: "private",
            display_recipient: [{id: 999999}],
        }),
    );
    assert(!predicate({type: "stream"}));

    predicate = get_predicate([["pm-with", "Joe@example.com,steve@foo.com"]]);
    assert(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );

    // Make sure your own email is ignored
    predicate = get_predicate([["pm-with", "Joe@example.com,steve@foo.com,me@example.com"]]);
    assert(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );

    predicate = get_predicate([["pm-with", "nobody@example.com"]]);
    assert(
        !predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}],
        }),
    );

    predicate = get_predicate([["group-pm-with", "nobody@example.com"]]);
    assert(
        !predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}],
        }),
    );

    predicate = get_predicate([["group-pm-with", "Joe@example.com"]]);
    assert(
        predicate({
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}, {id: me.user_id}],
        }),
    );
    assert(
        !predicate({
            // you must be a part of the group pm
            type: "private",
            display_recipient: [{id: joe.user_id}, {id: steve.user_id}],
        }),
    );
    assert(
        !predicate({
            type: "private",
            display_recipient: [{id: steve.user_id}, {id: me.user_id}],
        }),
    );
    assert(!predicate({type: "stream"}));

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
    assert(!predicate(img_msg));
    assert(!predicate(non_img_attachment_msg));
    assert(!predicate(link_msg));
    assert(!predicate(no_has_filter_matching_msg));

    // HTML content of message is used to determine if image have link, image or attachment.
    // We are using jquery to parse the html and find existence of relevant tags/elements.
    // In tests we need to stub the calls to jquery so using zjquery's .set_find_results method.
    function set_find_results_for_msg_content(msg, jquery_selector, results) {
        $(`<div>${msg.content}</div>`).set_find_results(jquery_selector, results);
    }

    const has_link = get_predicate([["has", "link"]]);
    set_find_results_for_msg_content(img_msg, "a", [$("<a>")]);
    assert(has_link(img_msg));
    set_find_results_for_msg_content(non_img_attachment_msg, "a", [$("<a>")]);
    assert(has_link(non_img_attachment_msg));
    set_find_results_for_msg_content(link_msg, "a", [$("<a>")]);
    assert(has_link(link_msg));
    set_find_results_for_msg_content(no_has_filter_matching_msg, "a", false);
    assert(!has_link(no_has_filter_matching_msg));

    const has_attachment = get_predicate([["has", "attachment"]]);
    set_find_results_for_msg_content(img_msg, "a[href^='/user_uploads']", [$("<a>")]);
    assert(has_attachment(img_msg));
    set_find_results_for_msg_content(non_img_attachment_msg, "a[href^='/user_uploads']", [
        $("<a>"),
    ]);
    assert(has_attachment(non_img_attachment_msg));
    set_find_results_for_msg_content(link_msg, "a[href^='/user_uploads']", false);
    assert(!has_attachment(link_msg));
    set_find_results_for_msg_content(no_has_filter_matching_msg, "a[href^='/user_uploads']", false);
    assert(!has_attachment(no_has_filter_matching_msg));

    const has_image = get_predicate([["has", "image"]]);
    set_find_results_for_msg_content(img_msg, ".message_inline_image", [$("<img>")]);
    assert(has_image(img_msg));
    set_find_results_for_msg_content(non_img_attachment_msg, ".message_inline_image", false);
    assert(!has_image(non_img_attachment_msg));
    set_find_results_for_msg_content(link_msg, ".message_inline_image", false);
    assert(!has_image(link_msg));
    set_find_results_for_msg_content(no_has_filter_matching_msg, ".message_inline_image", false);
    assert(!has_image(no_has_filter_matching_msg));
});

run_test("negated_predicates", () => {
    let predicate;
    let narrow;

    const social_stream_id = 555;
    make_sub("social", social_stream_id);

    narrow = [{operator: "stream", operand: "social", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert(predicate({type: "stream", stream_id: 999999}));
    assert(!predicate({type: "stream", stream_id: social_stream_id}));

    narrow = [{operator: "streams", operand: "public", negated: true}];
    predicate = new Filter(narrow).predicate();
    assert(predicate({}));
});

run_test("mit_exceptions", () => {
    global.page_params.realm_is_zephyr_mirror_realm = true;

    let predicate = get_predicate([
        ["stream", "Foo"],
        ["topic", "personal"],
    ]);
    assert(predicate({type: "stream", stream: "foo", topic: "personal"}));
    assert(predicate({type: "stream", stream: "foo.d", topic: "personal"}));
    assert(predicate({type: "stream", stream: "foo.d", topic: ""}));
    assert(!predicate({type: "stream", stream: "wrong"}));
    assert(!predicate({type: "stream", stream: "foo", topic: "whatever"}));
    assert(!predicate({type: "private"}));

    predicate = get_predicate([
        ["stream", "Foo"],
        ["topic", "bar"],
    ]);
    assert(predicate({type: "stream", stream: "foo", topic: "bar.d"}));

    // Try to get the MIT regex to explode for an empty stream.
    let terms = [
        {operator: "stream", operand: ""},
        {operator: "topic", operand: "bar"},
    ];
    predicate = new Filter(terms).predicate();
    assert(!predicate({type: "stream", stream: "foo", topic: "bar"}));

    // Try to get the MIT regex to explode for an empty topic.
    terms = [
        {operator: "stream", operand: "foo"},
        {operator: "topic", operand: ""},
    ];
    predicate = new Filter(terms).predicate();
    assert(!predicate({type: "stream", stream: "foo", topic: "bar"}));
});

run_test("predicate_edge_cases", () => {
    let predicate;
    // The code supports undefined as an operator to Filter, which results
    // in a predicate that accepts any message.
    predicate = new Filter().predicate();
    assert(predicate({}));

    // Upstream code should prevent Filter.predicate from being called with
    // invalid operator/operand combinations, but right now we just silently
    // return a function that accepts all messages.
    predicate = get_predicate([["in", "bogus"]]);
    assert(predicate({}));

    predicate = get_predicate([["bogus", 33]]);
    assert(predicate({}));

    predicate = get_predicate([["is", "bogus"]]);
    assert(predicate({}));

    // Exercise caching feature.
    const terms = [
        {operator: "stream", operand: "Foo"},
        {operator: "topic", operand: "bar"},
    ];
    const filter = new Filter(terms);
    filter.predicate();
    predicate = filter.predicate(); // get cached version
    assert(predicate({type: "stream", stream: "foo", topic: "bar"}));
});

run_test("parse", () => {
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

    string = "pm-with:leo+test@zulip.com";
    operators = [{operator: "pm-with", operand: "leo+test@zulip.com"}];
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
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: "text more text"},
    ];
    _test();

    string = "text streams:public more text";
    operators = [
        {operator: "streams", operand: "public"},
        {operator: "search", operand: "text more text"},
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
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: ":stream: :emoji: are cool"},
    ];
    _test();

    string = ":stream: stream:foo -:emoji: are cool";
    operators = [
        {operator: "stream", operand: "foo"},
        {operator: "search", operand: ":stream: -:emoji: are cool"},
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

run_test("unparse", () => {
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

run_test("describe", () => {
    let narrow;
    let string;

    narrow = [{operator: "streams", operand: "public"}];
    string = "streams public";
    assert.equal(Filter.describe(narrow), string);

    narrow = [{operator: "streams", operand: "public", negated: true}];
    string = "exclude streams public";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "is", operand: "starred"},
    ];
    string = "stream devel, starred messages";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "stream", operand: "river"},
        {operator: "is", operand: "unread"},
    ];
    string = "stream river, unread messages";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "JS"},
    ];
    string = "stream devel &gt; JS";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "is", operand: "private"},
        {operator: "search", operand: "lunch"},
    ];
    string = "private messages, search for lunch";
    assert.equal(Filter.describe(narrow), string);

    narrow = [{operator: "id", operand: 99}];
    string = "message ID 99";
    assert.equal(Filter.describe(narrow), string);

    narrow = [{operator: "in", operand: "home"}];
    string = "messages in home";
    assert.equal(Filter.describe(narrow), string);

    narrow = [{operator: "is", operand: "mentioned"}];
    string = "@-mentions";
    assert.equal(Filter.describe(narrow), string);

    narrow = [{operator: "is", operand: "alerted"}];
    string = "alerted messages";
    assert.equal(Filter.describe(narrow), string);

    narrow = [{operator: "is", operand: "something_we_do_not_support"}];
    string = "invalid something_we_do_not_support operand for is operator";
    assert.equal(Filter.describe(narrow), string);

    // this should be unreachable, but just in case
    narrow = [{operator: "bogus", operand: "foo"}];
    string = "unknown operator";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "topic", operand: "JS", negated: true},
    ];
    string = "stream devel, exclude topic JS";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "is", operand: "private"},
        {operator: "search", operand: "lunch", negated: true},
    ];
    string = "private messages, exclude lunch";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "is", operand: "starred", negated: true},
    ];
    string = "stream devel, exclude starred messages";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "stream", operand: "devel"},
        {operator: "has", operand: "image", negated: true},
    ];
    string = "stream devel, exclude messages with one or more image";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "has", operand: "abc", negated: true},
        {operator: "stream", operand: "devel"},
    ];
    string = "invalid abc operand for has operator, stream devel";
    assert.equal(Filter.describe(narrow), string);

    narrow = [
        {operator: "has", operand: "image", negated: true},
        {operator: "stream", operand: "devel"},
    ];
    string = "exclude messages with one or more image, stream devel";
    assert.equal(Filter.describe(narrow), string);

    narrow = [];
    string = "all messages";
    assert.equal(Filter.describe(narrow), string);
});

run_test("can_bucket_by", () => {
    let terms = [{operator: "stream", operand: "My Stream"}];
    let filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), true);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("pm-with"), false);

    terms = [
        // try a non-orthodox ordering
        {operator: "topic", operand: "My Topic"},
        {operator: "stream", operand: "My Stream"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), true);
    assert.equal(filter.can_bucket_by("stream", "topic"), true);
    assert.equal(filter.can_bucket_by("pm-with"), false);

    terms = [
        {operator: "stream", operand: "My Stream", negated: true},
        {operator: "topic", operand: "My Topic"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), false);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("pm-with"), false);

    terms = [{operator: "pm-with", operand: "foo@example.com", negated: true}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), false);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("pm-with"), false);

    terms = [{operator: "pm-with", operand: "foo@example.com,bar@example.com"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("stream"), false);
    assert.equal(filter.can_bucket_by("stream", "topic"), false);
    assert.equal(filter.can_bucket_by("pm-with"), true);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-private"), false);

    terms = [{operator: "is", operand: "private"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-private"), true);

    terms = [{operator: "is", operand: "mentioned"}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), true);
    assert.equal(filter.can_bucket_by("is-private"), false);

    terms = [
        {operator: "is", operand: "mentioned"},
        {operator: "is", operand: "starred"},
    ];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), true);
    assert.equal(filter.can_bucket_by("is-private"), false);

    // The call below returns false for somewhat arbitrary
    // reasons -- we say is-private has precedence over
    // is-starred.
    assert.equal(filter.can_bucket_by("is-starred"), false);

    terms = [{operator: "is", operand: "mentioned", negated: true}];
    filter = new Filter(terms);
    assert.equal(filter.can_bucket_by("is-mentioned"), false);
    assert.equal(filter.can_bucket_by("is-private"), false);
});

run_test("term_type", () => {
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
    assert_term_type(term("pm-with", "whomever"), "pm-with");
    assert_term_type(term("pm-with", "whomever", true), "not-pm-with");
    assert_term_type(term("is", "private"), "is-private");
    assert_term_type(term("has", "link"), "has-link");
    assert_term_type(term("has", "attachment", true), "not-has-attachment");

    function assert_term_sort(in_terms, expected) {
        const sorted_terms = Filter.sorted_term_types(in_terms);
        assert.deepEqual(sorted_terms, expected);
    }

    assert_term_sort(["topic", "stream", "sender"], ["stream", "topic", "sender"]);

    assert_term_sort(
        ["has-link", "near", "is-unread", "pm-with"],
        ["pm-with", "near", "is-unread", "has-link"],
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
    assert(filter._build_sorted_term_types_called);

    // cached trial
    filter._build_sorted_term_types_called = false;
    const cached_terms = filter.sorted_term_types();
    assert.deepEqual(cached_terms, ["stream", "topic", "sender"]);
    assert(!filter._build_sorted_term_types_called);
});

run_test("first_valid_id_from", () => {
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

    message_store.get = () => {};

    assert.equal(filter.first_valid_id_from(msg_ids), undefined);

    message_store.get = (msg_id) => messages[msg_id];

    assert.equal(filter.first_valid_id_from(msg_ids), 20);
});

run_test("update_email", () => {
    const terms = [
        {operator: "pm-with", operand: "steve@foo.com"},
        {operator: "sender", operand: "steve@foo.com"},
        {operator: "stream", operand: "steve@foo.com"}, // try to be tricky
    ];
    const filter = new Filter(terms);
    filter.update_email(steve.user_id, "showell@foo.com");
    assert.deepEqual(filter.operands("pm-with"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("sender"), ["showell@foo.com"]);
    assert.deepEqual(filter.operands("stream"), ["steve@foo.com"]);
});

function make_private_sub(name, stream_id) {
    const sub = {
        name,
        stream_id,
        invite_only: true,
    };
    global.stream_data.add_sub(sub);
}

function make_web_public_sub(name, stream_id) {
    const sub = {
        name,
        stream_id,
        is_web_public: true,
    };
    global.stream_data.add_sub(sub);
}

run_test("navbar_helpers", () => {
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

    function test_get_icon(test_case) {
        const filter = new Filter(test_case.operator);
        assert.equal(filter.get_icon(), test_case.icon);
    }

    function test_get_title(test_case) {
        const filter = new Filter(test_case.operator);
        assert.deepEqual(filter.get_title(), test_case.title);
    }

    function test_helpers(test_case) {
        // debugging tip: add a `console.log(test_case)` here
        test_common_narrow(test_case);
        test_get_icon(test_case);
        test_get_title(test_case);
        test_redirect_url_with_search(test_case);
    }

    const in_home = [{operator: "in", operand: "home"}];
    const in_all = [{operator: "in", operand: "all"}];
    const is_starred = [{operator: "is", operand: "starred"}];
    const is_private = [{operator: "is", operand: "private"}];
    const is_mentioned = [{operator: "is", operand: "mentioned"}];
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
    const pm_with = [{operator: "pm-with", operand: "joe@example.com"}];
    const group_pm = [{operator: "pm-with", operand: "joe@example.com,STEVE@foo.com"}];
    const group_pm_including_missing_person = [
        {operator: "pm-with", operand: "joe@example.com,STEVE@foo.com,sally@doesnotexist.com"},
    ];

    const test_cases = [
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
            operator: is_private,
            is_common_narrow: true,
            icon: "envelope",
            title: "translated: Private messages",
            redirect_url_with_search: "/#narrow/is/private",
        },
        {
            operator: is_mentioned,
            is_common_narrow: true,
            icon: "at",
            title: "translated: Mentions",
            redirect_url_with_search: "/#narrow/is/mentioned",
        },
        {
            operator: stream_topic_operators,
            is_common_narrow: true,
            icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "/#narrow/stream/42-Foo/topic/bar",
        },
        {
            operator: streams_public,
            is_common_narrow: true,
            icon: undefined,
            title: "translated: Public stream messages in organization",
            redirect_url_with_search: "/#narrow/streams/public",
        },
        {
            operator: stream_operator,
            is_common_narrow: true,
            icon: "hashtag",
            title: "Foo",
            redirect_url_with_search: "/#narrow/stream/42-Foo",
        },
        {
            operator: non_existent_stream,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown stream",
            redirect_url_with_search: "#",
        },
        {
            operator: non_existent_stream_topic,
            is_common_narrow: true,
            icon: "question-circle-o",
            title: "translated: Unknown stream",
            redirect_url_with_search: "#",
        },
        {
            operator: private_stream_operator,
            is_common_narrow: true,
            icon: "lock",
            title: "psub",
            redirect_url_with_search: "/#narrow/stream/22-psub",
        },
        {
            operator: web_public_stream_operator,
            is_common_narrow: true,
            icon: "globe",
            title: "webPublicSub",
            redirect_url_with_search: "/#narrow/stream/12-webPublicSub",
        },
        {
            operator: pm_with,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([joe.full_name]),
            redirect_url_with_search:
                "/#narrow/pm-with/" + joe.user_id + "-" + joe.email.split("@")[0],
        },
        {
            operator: group_pm,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([joe.full_name, steve.full_name]),
            redirect_url_with_search:
                "/#narrow/pm-with/" + joe.user_id + "," + steve.user_id + "-group",
        },
        {
            operator: group_pm_including_missing_person,
            is_common_narrow: true,
            icon: "envelope",
            title: properly_separated_names([
                joe.full_name,
                steve.full_name,
                "sally@doesnotexist.com",
            ]),
            redirect_url_with_search: "/#narrow/pm-with/undefined",
        },
    ];

    test_cases.forEach((test_case) => {
        test_helpers(test_case);
    });

    // TODO: these may be removed, based on design decisions
    const sender_me = [{operator: "sender", operand: "me"}];
    const sender_joe = [{operator: "sender", operand: joe.email}];

    const redirect_edge_cases = [
        {
            operator: sender_me,
            redirect_url_with_search:
                "/#narrow/sender/" + me.user_id + "-" + me.email.split("@")[0],
            is_common_narrow: false,
        },
        {
            operator: sender_joe,
            redirect_url_with_search:
                "/#narrow/sender/" + joe.user_id + "-" + joe.email.split("@")[0],
            is_common_narrow: false,
        },
    ];

    redirect_edge_cases.forEach((test_case) => {
        test_redirect_url_with_search(test_case);
    });

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
        title: "Foo",
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

run_test("error_cases", () => {
    // This test just gives us 100% line coverage on defensive code that
    // should not be reached unless we break other code.
    people.pm_with_user_ids = function () {};

    const predicate = get_predicate([["pm-with", "Joe@example.com"]]);
    assert(!predicate({type: "private"}));
});

"use strict";

const assert = require("node:assert/strict");

const _ = require("lodash");
const MockDate = require("mockdate");

const {set_global, with_overrides, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const blueslip = zrequire("blueslip");
const {set_realm} = zrequire("state_data");
const {initialize_user_settings} = zrequire("user_settings");

const realm = {};
set_realm(realm);

set_global("document", {});
const util = zrequire("util");

initialize_user_settings({user_settings: {}});

run_test("CachedValue", () => {
    let x = 5;

    const cv = new util.CachedValue({
        compute_value() {
            return x * 2;
        },
    });

    assert.equal(cv.get(), 10);

    x = 6;
    assert.equal(cv.get(), 10);
    cv.reset();
    assert.equal(cv.get(), 12);
});

run_test("extract_pm_recipients", () => {
    assert.equal(util.extract_pm_recipients("bob@foo.com, alice@foo.com").length, 2);
    assert.equal(util.extract_pm_recipients("bob@foo.com, ").length, 1);
});

run_test("lower_bound", () => {
    const arr = [{x: 10}, {x: 20}, {x: 30}, {x: 40}, {x: 50}];

    function compare(a, b) {
        return a.x < b;
    }

    assert.equal(util.lower_bound(arr, 5, compare), 0);
    assert.equal(util.lower_bound(arr, 10, compare), 0);
    assert.equal(util.lower_bound(arr, 15, compare), 1);
    assert.equal(util.lower_bound(arr, 50, compare), 4);
    assert.equal(util.lower_bound(arr, 55, compare), 5);
});

run_test("lower_same", () => {
    assert.ok(util.lower_same("abc", "AbC"));
    assert.ok(!util.lower_same("abbc", "AbC"));

    blueslip.expect("error", "Cannot compare strings; at least one value is undefined");
    util.lower_same("abc", undefined);
});

run_test("same_recipient", () => {
    assert.ok(
        util.same_recipient(
            {type: "stream", stream_id: 101, topic: "Bar"},
            {type: "stream", stream_id: 101, topic: "bar"},
        ),
    );

    assert.ok(
        !util.same_recipient(
            {type: "stream", stream_id: 101, topic: "Bar"},
            {type: "stream", stream_id: 102, topic: "whatever"},
        ),
    );

    assert.ok(
        util.same_recipient(
            {type: "private", to_user_ids: "101,102"},
            {type: "private", to_user_ids: "101,102"},
        ),
    );

    assert.ok(
        !util.same_recipient(
            {type: "private", to_user_ids: "101,102"},
            {type: "private", to_user_ids: "103"},
        ),
    );

    assert.ok(
        !util.same_recipient({type: "stream", stream_id: 101, topic: "Bar"}, {type: "private"}),
    );

    assert.ok(!util.same_recipient({type: "private", to_user_ids: undefined}, {type: "private"}));

    assert.ok(!util.same_recipient(undefined, {type: "private"}));

    assert.ok(!util.same_recipient(undefined, undefined));
});

run_test("robust_url_decode", ({override}) => {
    assert.equal(util.robust_url_decode("xxx%3Ayyy"), "xxx:yyy");
    assert.equal(util.robust_url_decode("xxx%3"), "xxx");

    override(global, "decodeURIComponent", () => {
        throw new Error("foo");
    });
    assert.throws(
        () => {
            util.robust_url_decode("%E0%A4%A");
        },
        {name: "Error", message: "foo"},
    );
});

run_test("dumb_strcmp", ({override}) => {
    override(Intl, "Collator", undefined);
    const strcmp = util.make_strcmp();
    assert.equal(strcmp("a", "b"), -1);
    assert.equal(strcmp("c", "c"), 0);
    assert.equal(strcmp("z", "y"), 1);
});

run_test("get_edit_event_orig_topic", () => {
    assert.equal(util.get_edit_event_orig_topic({orig_subject: "lunch"}), "lunch");
});

run_test("is_mobile", () => {
    window.navigator = {userAgent: "Android"};
    assert.ok(util.is_mobile());

    window.navigator = {userAgent: "Not mobile"};
    assert.ok(!util.is_mobile());
});

run_test("array_compare", () => {
    assert.ok(util.array_compare([], []));
    assert.ok(util.array_compare([1, 2, 3], [1, 2, 3]));
    assert.ok(!util.array_compare([1, 2], [1, 2, 3]));
    assert.ok(!util.array_compare([1, 2, 3], [1, 2]));
    assert.ok(!util.array_compare([1, 2, 3, 4], [1, 2, 3, 5]));
});

run_test("normalize_recipients", () => {
    assert.equal(
        util.normalize_recipients("ZOE@foo.com, bob@foo.com, alice@foo.com, AARON@foo.com "),
        "aaron@foo.com,alice@foo.com,bob@foo.com,zoe@foo.com",
    );
});

run_test("random_int", () => {
    const min = 0;
    const max = 100;

    _.times(500, () => {
        const val = util.random_int(min, max);
        assert.ok(min <= val);
        assert.ok(val <= max);
        assert.equal(val, Math.floor(val));
    });
});

run_test("wildcard_mentions_regexp", () => {
    const messages_with_all_mentions = [
        "@**all**",
        "some text before @**all** some text after",
        "@**all** some text after only",
        "some text before only @**all**",
    ];

    const messages_with_everyone_mentions = [
        "@**everyone**",
        '"@**everyone**"',
        "@**everyone**: Look at this!",
        "The <@**everyone**> channel",
        'I have to say "@**everyone**" to ding the bell',
        "some text before @**everyone** some text after",
        "@**everyone** some text after only",
        "some text before only @**everyone**",
    ];

    const messages_with_stream_mentions = [
        "@**stream**",
        "some text before @**stream** some text after",
        "@**stream** some text after only",
        "some text before only @**stream**",
    ];

    const messages_with_channel_mentions = [
        "@**channel**",
        "some text before @**channel** some text after",
        "@**channel** some text after only",
        "some text before only @**channel**",
    ];

    const messages_with_topic_mentions = [
        "@**topic**",
        "some text before @**topic** some text after",
        "@**topic** some text after only",
        "some text before only @**topic**",
    ];

    const messages_without_all_mentions = [
        "@all",
        "some text before @all some text after",
        "`@everyone`",
        "some_email@everyone.com",
        "`@**everyone**`",
        "some_email@**everyone**.com",
    ];

    const messages_without_everyone_mentions = [
        "some text before @everyone some text after",
        "@everyone",
        "`@everyone`",
        "some_email@everyone.com",
        "`@**everyone**`",
        "some_email@**everyone**.com",
    ];

    const messages_without_stream_mentions = [
        "some text before @stream some text after",
        "@stream",
        "`@stream`",
        "some_email@stream.com",
        "`@**stream**`",
        "some_email@**stream**.com",
    ];

    const messages_without_channel_mentions = [
        "some text before @channel some text after",
        "@channel",
        "`@channel`",
        "some_email@channel.com",
        "`@**channel**`",
        "some_email@**channel**.com",
    ];

    let i;
    for (i = 0; i < messages_with_all_mentions.length; i += 1) {
        assert.ok(util.find_stream_wildcard_mentions(messages_with_all_mentions[i]));
    }

    for (i = 0; i < messages_with_everyone_mentions.length; i += 1) {
        assert.ok(util.find_stream_wildcard_mentions(messages_with_everyone_mentions[i]));
    }

    for (i = 0; i < messages_with_stream_mentions.length; i += 1) {
        assert.ok(util.find_stream_wildcard_mentions(messages_with_stream_mentions[i]));
    }

    for (i = 0; i < messages_with_channel_mentions.length; i += 1) {
        assert.ok(util.find_stream_wildcard_mentions(messages_with_channel_mentions[i]));
    }

    for (i = 0; i < messages_with_topic_mentions.length; i += 1) {
        assert.ok(!util.find_stream_wildcard_mentions(messages_with_topic_mentions[i]));
    }

    for (i = 0; i < messages_without_all_mentions.length; i += 1) {
        assert.ok(!util.find_stream_wildcard_mentions(messages_without_everyone_mentions[i]));
    }

    for (i = 0; i < messages_without_everyone_mentions.length; i += 1) {
        assert.ok(!util.find_stream_wildcard_mentions(messages_without_everyone_mentions[i]));
    }

    for (i = 0; i < messages_without_stream_mentions.length; i += 1) {
        assert.ok(!util.find_stream_wildcard_mentions(messages_without_stream_mentions[i]));
    }

    for (i = 0; i < messages_without_channel_mentions.length; i += 1) {
        assert.ok(!util.find_stream_wildcard_mentions(messages_without_channel_mentions[i]));
    }
});

run_test("move_array_elements_to_front", () => {
    const strings = ["string1", "string3", "string2", "string4"];
    const strings_selection = ["string4", "string1"];
    const strings_expected = ["string1", "string4", "string3", "string2"];
    const strings_no_selection = util.move_array_elements_to_front(strings, []);
    const strings_no_array = util.move_array_elements_to_front([], strings_selection);
    const strings_actual = util.move_array_elements_to_front(strings, strings_selection);
    const emails = [
        "test@zulip.com",
        "test@test.com",
        "test@localhost",
        "test@invalid@email",
        "something@zulip.com",
    ];
    const emails_selection = ["test@test.com", "test@localhost", "test@invalid@email"];
    const emails_expected = [
        "test@test.com",
        "test@localhost",
        "test@invalid@email",
        "test@zulip.com",
        "something@zulip.com",
    ];
    const emails_actual = util.move_array_elements_to_front(emails, emails_selection);
    assert.deepEqual(strings_no_selection, strings);
    assert.deepEqual(strings_no_array, []);
    assert.deepEqual(strings_actual, strings_expected);
    assert.deepEqual(emails_actual, emails_expected);
});

run_test("filter_by_word_prefix_match", () => {
    const strings = ["stream-hyphen_underscore/slash", "three word stream"];
    const values = [0, 1];
    const item_to_string = (idx) => strings[idx];

    // Default settings will match words with a space delimiter before them.
    assert.deepEqual(util.filter_by_word_prefix_match(values, "stream", item_to_string), [0, 1]);
    assert.deepEqual(util.filter_by_word_prefix_match(values, "word stream", item_to_string), [1]);

    // Since - appears before `hyphen` in
    // stream-hyphen_underscore/slash, we require `-` in the set of
    // characters for it to match.
    assert.deepEqual(util.filter_by_word_prefix_match(values, "hyphe", item_to_string), []);
    assert.deepEqual(util.filter_by_word_prefix_match(values, "hyphe", item_to_string, /[\s/_-]/), [
        0,
    ]);
    assert.deepEqual(util.filter_by_word_prefix_match(values, "hyphe", item_to_string, /[\s-]/), [
        0,
    ]);

    // Similarly `_` must be in the set of allowed characters to match "underscore".
    assert.deepEqual(util.filter_by_word_prefix_match(values, "unders", item_to_string, /[\s_]/), [
        0,
    ]);
    assert.deepEqual(util.filter_by_word_prefix_match(values, "unders", item_to_string, /\s/), []);
});

run_test("get_string_diff", () => {
    assert.deepEqual(
        util.get_string_diff("#ann is for updates", "#**announce** is for updates"),
        [1, 4, 13],
    );
    assert.deepEqual(util.get_string_diff("/p", "/poll"), [2, 2, 5]);
    assert.deepEqual(util.get_string_diff("Hey @Aa", "Hey @**aaron** "), [5, 7, 15]);
    assert.deepEqual(util.get_string_diff("same", "same"), [0, 0, 0]);
    assert.deepEqual(util.get_string_diff("same-end", "two same-end"), [0, 0, 4]);
    assert.deepEqual(util.get_string_diff("space", "sp ace"), [2, 2, 3]);
});

run_test("is_valid_url", () => {
    assert.equal(util.is_valid_url("http://"), false);
    assert.equal(util.is_valid_url("random_string"), true);
    assert.equal(util.is_valid_url("http://google.com/something?q=query#hash"), true);
    assert.equal(util.is_valid_url("/abc/"), true);

    assert.equal(util.is_valid_url("http://", true), false);
    assert.equal(util.is_valid_url("random_string", true), false);
    assert.equal(util.is_valid_url("http://google.com/something?q=query#hash", true), true);
    assert.equal(util.is_valid_url("/abc/", true), false);
});

run_test("format_array_as_list", () => {
    const array = ["apple", "banana", "orange"];
    // when Intl exist
    assert.equal(
        util.format_array_as_list(array, "long", "conjunction"),
        "apple, banana, and orange",
    );
    assert.equal(
        util.format_array_as_list_with_highlighted_elements(array, "long", "conjunction"),
        '<b class="highlighted-element">apple</b>, <b class="highlighted-element">banana</b>, and <b class="highlighted-element">orange</b>',
    );

    // Conjunction format
    assert.equal(
        util.format_array_as_list_with_conjunction(array, "narrow"),
        "apple, banana, orange",
    );
    assert.equal(
        util.format_array_as_list_with_conjunction(array, "long"),
        "apple, banana, and orange",
    );

    // when Intl.ListFormat does not exist
    with_overrides(({override}) => {
        override(global.Intl, "ListFormat", undefined);
        assert.equal(
            util.format_array_as_list(array, "long", "conjunction"),
            "apple, banana, orange",
        );
        assert.equal(
            util.format_array_as_list_with_highlighted_elements(array, "long", "conjunction"),
            '<b class="highlighted-element">apple</b>, <b class="highlighted-element">banana</b>, <b class="highlighted-element">orange</b>',
        );

        assert.equal(
            util.format_array_as_list_with_conjunction(array, "narrow"),
            "apple, banana, orange",
        );
        assert.equal(
            util.format_array_as_list_with_conjunction(array, "long"),
            "apple, banana, orange",
        );
    });
});

run_test("get_remaining_time", () => {
    // When current time is less than start time
    // Set a random start time
    const start_time = new Date(1000).getTime();
    // Set current time to 400ms ahead of the start time
    MockDate.set(start_time + 400);
    const duration = 500;
    let expected_remaining_time = 100;
    assert.equal(util.get_remaining_time(start_time, duration), expected_remaining_time);

    // When current time is greater than start time + duration
    // Set current time to 100ms after the start time + duration
    MockDate.set(start_time + duration + 100);
    expected_remaining_time = 0;
    assert.equal(util.get_remaining_time(start_time, duration), expected_remaining_time);

    MockDate.reset();
});

run_test("get_custom_time_in_minutes", () => {
    const time_input = 15;
    assert.equal(util.get_custom_time_in_minutes("weeks", time_input), time_input * 7 * 24 * 60);
    assert.equal(util.get_custom_time_in_minutes("days", time_input), time_input * 24 * 60);
    assert.equal(util.get_custom_time_in_minutes("hours", time_input), time_input * 60);
    assert.equal(util.get_custom_time_in_minutes("minutes", time_input), time_input);
    // Unknown time unit string throws an error, but we still return
    // the time input that was passed to the function.
    blueslip.expect("error", "Unexpected custom time unit: invalid");
    assert.equal(util.get_custom_time_in_minutes("invalid", time_input), time_input);
    /// NaN time input returns NaN
    const invalid_time_input = Number.NaN;
    assert.equal(util.get_custom_time_in_minutes("hours", invalid_time_input), invalid_time_input);
});

run_test("check_and_validate_custom_time_input", () => {
    const input_is_zero = 0;
    let checked_input = util.check_time_input(input_is_zero);
    assert.equal(checked_input, 0);
    assert.equal(util.validate_custom_time_input(checked_input, true), true);
    assert.equal(util.validate_custom_time_input(checked_input, false), false);

    const input_is_nan = "24abc";
    checked_input = util.check_time_input(input_is_nan);
    assert.equal(checked_input, Number.NaN);
    assert.equal(util.validate_custom_time_input(checked_input), false);

    const input_is_negative = "-24";
    checked_input = util.check_time_input(input_is_negative);
    assert.equal(checked_input, -24);
    assert.equal(util.validate_custom_time_input(input_is_negative), false);

    const input_is_float = "24.5";
    checked_input = util.check_time_input(input_is_float);
    assert.equal(checked_input, 24);
    checked_input = util.check_time_input(input_is_float, true);
    assert.equal(checked_input, 24.5);
    assert.equal(util.validate_custom_time_input(input_is_float), true);

    const input_is_integer = "10";
    checked_input = util.check_time_input(input_is_integer);
    assert.equal(checked_input, 10);
    assert.equal(util.validate_custom_time_input(input_is_integer), true);
});

run_test("the", () => {
    const list_with_one_item = ["foo"];
    assert.equal(util.the(list_with_one_item), "foo");

    blueslip.expect("error", "the: expected only 1 item, got more");
    const list_with_more_items = ["foo", "bar"];
    // Error is thrown, but we still return the first item to avoid
    // unnecessarily breaking the app.
    assert.equal(util.the(list_with_more_items), "foo");

    blueslip.expect("error", "the: expected only 1 item, got none");
    // Error is thrown, but we still return the "first" item to avoid
    // unnecessarily breaking the app for places we refactored this that
    // were previously typed wrong but not breaking the app.
    assert.equal(util.the([]), undefined);
});

run_test("compare_a_b", () => {
    const user1 = {
        id: 1,
        name: "sally",
    };
    const user2 = {
        id: 2,
        name: "jenny",
    };
    const user3 = {
        id: 3,
        name: "max",
    };
    const user4 = {
        id: 4,
        name: "max",
    };
    const unsorted = [user2, user1, user4, user3];

    const sorted_by_id = [...unsorted].sort((a, b) => util.compare_a_b(a.id, b.id));
    assert.deepEqual(sorted_by_id, [user1, user2, user3, user4]);

    const sorted_by_name = [...unsorted].sort((a, b) => util.compare_a_b(a.name, b.name));
    assert.deepEqual(sorted_by_name, [user2, user4, user3, user1]);
});

run_test("get_final_topic_display_name", ({override}) => {
    // When the topic name is not an empty string,
    // the displayed topic name matches the actual topic name.
    assert.deepEqual(util.get_final_topic_display_name("not empty string"), "not empty string");

    // When the topic name is an empty string, there are two possible scenarios:
    // 1. The `realm_empty_topic_display_name` setting has its default value
    //    "general chat". In this case, the topic is displayed as the translated
    //    value of "general chat" based on the user's language settings.
    // 2. The `realm_empty_topic_display_name` setting has been customized by
    //    an admin. In this case, the topic is displayed using the value of
    //    `realm_empty_topic_display_name` without any translation.
    override(realm, "realm_empty_topic_display_name", "general chat");
    assert.deepEqual(util.get_final_topic_display_name(""), "translated: general chat");
    override(realm, "realm_empty_topic_display_name", "random topic name");
    assert.deepEqual(util.get_final_topic_display_name(""), "random topic name");
});

run_test("is_topic_name_considered_empty", ({override}) => {
    // Topic is not considered empty if it is distinct string
    // other than "(no topic)", or the displayed topic name for empty string.
    assert.ok(!util.is_topic_name_considered_empty("some topic"));

    // Topic is considered empty if it is an empty string.
    assert.ok(util.is_topic_name_considered_empty(""));

    // Topic is considered empty if it is equal to "(no topic)".
    assert.ok(util.is_topic_name_considered_empty("(no topic)"));

    // Topic name is considered empty if it is equal to the displayed
    // topic name for empty string.
    override(realm, "realm_empty_topic_display_name", "general chat");
    assert.ok(util.is_topic_name_considered_empty("translated: general chat"));
});

run_test("get_retry_backoff_seconds", () => {
    const xhr_500_error = {
        status: 500,
    };

    // Shorter backoff scale
    // First retry should be between 1-2 seconds.
    let backoff = util.get_retry_backoff_seconds(xhr_500_error, 1, true);
    assert.ok(backoff >= 1);
    assert.ok(backoff < 3);
    // 100th retry should be between 16-32 seconds.
    backoff = util.get_retry_backoff_seconds(xhr_500_error, 100, true);
    assert.ok(backoff >= 16);
    assert.ok(backoff <= 32);

    // Longer backoff scale
    // First retry should be between 1-2 seconds.
    backoff = util.get_retry_backoff_seconds(xhr_500_error, 1);
    assert.ok(backoff >= 1);
    assert.ok(backoff <= 3);
    // 100th retry should be between 45-90 seconds.
    backoff = util.get_retry_backoff_seconds(xhr_500_error, 100);
    assert.ok(backoff >= 45);
    assert.ok(backoff <= 90);

    const xhr_rate_limit_error = {
        status: 429,
        responseJSON: {
            code: "RATE_LIMIT_HIT",
            msg: "API usage exceeded rate limit",
            result: "error",
            "retry-after": 28.706807374954224,
        },
    };
    // First retry should be greater than the retry-after value.
    backoff = util.get_retry_backoff_seconds(xhr_rate_limit_error, 1);
    assert.ok(backoff >= 28.706807374954224);
    // 100th retry should be between 45-90 seconds.
    backoff = util.get_retry_backoff_seconds(xhr_rate_limit_error, 100);
    assert.ok(backoff >= 45);
    assert.ok(backoff <= 90);
});

run_test("sha256_hash", async ({override}) => {
    const expected_hash = "f8e27cb511cd469712e3e0f2ac05a990481c0a39e11830b4f6aee729a894b769";
    const data = "@*hamlet_and_cordelia* and #**channel>topic**";
    let hash = await util.sha256_hash(data);
    assert.equal(hash, undefined);
    override(window, "isSecureContext", true);
    hash = await util.sha256_hash(data);
    assert.equal(hash, expected_hash);
});

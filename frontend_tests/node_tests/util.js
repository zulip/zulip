"use strict";

const {JSDOM} = require("jsdom");
const _ = require("lodash");

set_global("$", global.make_zjquery());
set_global("DOMParser", new JSDOM().window.DOMParser);
set_global("document", {});
const util = zrequire("util");

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

run_test("get_reload_topic", () => {
    assert.equal(util.get_reload_topic({subject: "foo"}), "foo");
    assert.equal(util.get_reload_topic({topic: "bar"}), "bar");
});

run_test("extract_pm_recipients", () => {
    assert.equal(util.extract_pm_recipients("bob@foo.com, alice@foo.com").length, 2);
    assert.equal(util.extract_pm_recipients("bob@foo.com, ").length, 1);
});

run_test("is_pm_recipient", () => {
    const message = {to_user_ids: "31,32,33"};
    assert(util.is_pm_recipient(31, message));
    assert(util.is_pm_recipient(32, message));
    assert(!util.is_pm_recipient(34, message));
});

run_test("lower_bound", () => {
    let arr = [10, 20, 30, 40, 50];
    assert.equal(util.lower_bound(arr, 5), 0);
    assert.equal(util.lower_bound(arr, 10), 0);
    assert.equal(util.lower_bound(arr, 15), 1);
    assert.equal(util.lower_bound(arr, 50), 4);
    assert.equal(util.lower_bound(arr, 55), 5);
    assert.equal(util.lower_bound(arr, 2, 4, 31), 3);

    arr = [{x: 10}, {x: 20}, {x: 30}];

    function compare(a, b) {
        return a.x < b;
    }

    assert.equal(util.lower_bound(arr, 5, compare), 0);
    assert.equal(util.lower_bound(arr, 10, compare), 0);
    assert.equal(util.lower_bound(arr, 15, compare), 1);
});

run_test("same_recipient", () => {
    assert(
        util.same_recipient(
            {type: "stream", stream_id: 101, topic: "Bar"},
            {type: "stream", stream_id: 101, topic: "bar"},
        ),
    );

    assert(
        !util.same_recipient(
            {type: "stream", stream_id: 101, topic: "Bar"},
            {type: "stream", stream_id: 102, topic: "whatever"},
        ),
    );

    assert(
        util.same_recipient(
            {type: "private", to_user_ids: "101,102"},
            {type: "private", to_user_ids: "101,102"},
        ),
    );

    assert(
        !util.same_recipient(
            {type: "private", to_user_ids: "101,102"},
            {type: "private", to_user_ids: "103"},
        ),
    );

    assert(!util.same_recipient({type: "stream", stream_id: 101, topic: "Bar"}, {type: "private"}));

    assert(!util.same_recipient({type: "private", to_user_ids: undefined}, {type: "private"}));

    assert(!util.same_recipient({type: "unknown type"}, {type: "unknown type"}));

    assert(!util.same_recipient(undefined, {type: "private"}));

    assert(!util.same_recipient(undefined, undefined));
});

run_test("robust_uri_decode", () => {
    assert.equal(util.robust_uri_decode("xxx%3Ayyy"), "xxx:yyy");
    assert.equal(util.robust_uri_decode("xxx%3"), "xxx");

    set_global("decodeURIComponent", () => {
        throw new Error("foo");
    });
    try {
        util.robust_uri_decode("%E0%A4%A");
    } catch (error) {
        assert.equal(error.message, "foo");
    }
});

run_test("dumb_strcmp", () => {
    with_field(Intl, "Collator", undefined, () => {
        const strcmp = util.make_strcmp();
        assert.equal(strcmp("a", "b"), -1);
        assert.equal(strcmp("c", "c"), 0);
        assert.equal(strcmp("z", "y"), 1);
    });
});

run_test("get_edit_event_orig_topic", () => {
    assert.equal(util.get_edit_event_orig_topic({orig_subject: "lunch"}), "lunch");
});

run_test("get_edit_event_prev_topic", () => {
    assert.equal(util.get_edit_event_prev_topic({prev_subject: "dinner"}), "dinner");
});

run_test("is_mobile", () => {
    global.window.navigator = {userAgent: "Android"};
    assert(util.is_mobile());

    global.window.navigator = {userAgent: "Not mobile"};
    assert(!util.is_mobile());
});

run_test("array_compare", () => {
    assert(util.array_compare([], []));
    assert(util.array_compare([1, 2, 3], [1, 2, 3]));
    assert(!util.array_compare([1, 2], [1, 2, 3]));
    assert(!util.array_compare([1, 2, 3], [1, 2]));
    assert(!util.array_compare([1, 2, 3, 4], [1, 2, 3, 5]));
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
        assert(min <= val);
        assert(val <= max);
        assert.equal(val, Math.floor(val));
    });
});

run_test("all_and_everyone_mentions_regexp", () => {
    const messages_with_all_mentions = [
        "@**all**",
        "some text before @**all** some text after",
        "@**all** some text after only",
        "some text before only @**all**",
    ];

    const messages_with_everyone_mentions = [
        "@**everyone**",
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

    let i;
    for (i = 0; i < messages_with_all_mentions.length; i += 1) {
        assert(util.find_wildcard_mentions(messages_with_all_mentions[i]));
    }

    for (i = 0; i < messages_with_everyone_mentions.length; i += 1) {
        assert(util.find_wildcard_mentions(messages_with_everyone_mentions[i]));
    }

    for (i = 0; i < messages_with_stream_mentions.length; i += 1) {
        assert(util.find_wildcard_mentions(messages_with_stream_mentions[i]));
    }

    for (i = 0; i < messages_without_all_mentions.length; i += 1) {
        assert(!util.find_wildcard_mentions(messages_without_everyone_mentions[i]));
    }

    for (i = 0; i < messages_without_everyone_mentions.length; i += 1) {
        assert(!util.find_wildcard_mentions(messages_without_everyone_mentions[i]));
    }

    for (i = 0; i < messages_without_stream_mentions.length; i += 1) {
        assert(!util.find_wildcard_mentions(messages_without_stream_mentions[i]));
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
    let i;
    assert(strings_no_selection.length === strings.length);
    for (i = 0; i < strings_no_selection.length; i += 1) {
        assert(strings_no_selection[i] === strings[i]);
    }
    assert(strings_no_array.length === 0);
    assert(strings_actual.length === strings_expected.length);
    for (i = 0; i < strings_actual.length; i += 1) {
        assert(strings_actual[i] === strings_expected[i]);
    }
    assert(emails_actual.length === emails_expected.length);
    for (i = 0; i < emails_actual.length; i += 1) {
        assert(emails_actual[i] === emails_expected[i]);
    }
});

run_test("clean_user_content_links", () => {
    window.location.href = "http://zulip.zulipdev.com/";
    window.location.origin = "http://zulip.zulipdev.com";
    assert.equal(
        util.clean_user_content_links(
            '<a href="http://example.com">good</a> ' +
                '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png">upload</a> ' +
                '<a href="http://localhost:NNNN">invalid</a> ' +
                '<a href="javascript:alert(1)">unsafe</a> ' +
                '<a href="/#fragment" target="_blank">fragment</a>',
        ),
        '<a href="http://example.com" target="_blank" rel="noopener noreferrer" title="http://example.com/">good</a> ' +
            '<a href="http://zulip.zulipdev.com/user_uploads/w/ha/tever/file.png" target="_blank" rel="noopener noreferrer" title="file.png">upload</a> ' +
            "<a>invalid</a> " +
            "<a>unsafe</a> " +
            '<a href="/#fragment" title="http://zulip.zulipdev.com/#fragment">fragment</a>',
    );
});

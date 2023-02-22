"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const typeahead = zrequire("../shared/src/typeahead");

const unicode_emojis = [
    ["1f43c", "panda_face"],
    ["1f642", "smile"],
    ["1f604", "big_smile"],
    ["1f368", "ice_cream"],
    ["1f366", "soft_ice_cream"],
    ["1f6a5", "horizontal_traffic_light"],
    ["1f6a6", "traffic_light"],
    ["1f537", "large_blue_diamond"],
    ["1f539", "small_blue_diamond"],
];

const emojis = [
    {emoji_name: "japanese_post_office", reaction_type: "realm_emoji", url: "TBD"},
    {emoji_name: "tada", reaction_type: "realm_emoji", random_field: "whatever"},
    ...unicode_emojis.map(([emoji_code, emoji_name]) => ({
        emoji_name,
        emoji_code,
        reaction_type: "unicode_emoji",
    })),
];

function emoji_matches(query) {
    const matcher = typeahead.get_emoji_matcher(query);
    return emojis.filter((emoji) => matcher(emoji));
}

function assert_emoji_matches(query, expected) {
    const names = emoji_matches(query).map((emoji) => emoji.emoji_name);
    assert.deepEqual(names.sort(), expected);
}

run_test("get_emoji_matcher: nonmatches", () => {
    assert_emoji_matches("notaemoji", []);
    assert_emoji_matches("da_", []);
});

run_test("get_emoji_matcher: misc matches", () => {
    assert_emoji_matches("da", ["panda_face", "tada"]);
    assert_emoji_matches("smil", ["big_smile", "smile"]);
    assert_emoji_matches("mile", ["big_smile", "smile"]);
    assert_emoji_matches("japanese_post_", ["japanese_post_office"]);
});

run_test("matches starting at non-first word, too", () => {
    assert_emoji_matches("ice_cream", ["ice_cream", "soft_ice_cream"]);
    assert_emoji_matches("blue_dia", ["large_blue_diamond", "small_blue_diamond"]);
    assert_emoji_matches("traffic_", ["horizontal_traffic_light", "traffic_light"]);
});

run_test("matches literal unicode emoji", () => {
    assert_emoji_matches("🐼", ["panda_face"]);
});

run_test("get_emoji_matcher: spaces equivalent to underscores", () => {
    function assert_equivalent(query) {
        assert.deepEqual(emoji_matches(query), emoji_matches(query.replace(" ", "_")));
    }
    assert_equivalent("da ");
    assert_equivalent("panda ");
    assert_equivalent("japanese post ");
    assert_equivalent("ice ");
    assert_equivalent("ice cream");
    assert_equivalent("blue dia");
    assert_equivalent("traffic ");
    assert_equivalent("traffic l");
});

run_test("triage", () => {
    const alice = {name: "alice"};
    const alicia = {name: "Alicia"};
    const joan = {name: "Joan"};
    const jo = {name: "Jo"};
    const steve = {name: "steve"};
    const stephanie = {name: "Stephanie"};

    const names = [alice, alicia, joan, jo, steve, stephanie];

    assert.deepEqual(
        typeahead.triage("a", names, (r) => r.name),
        {
            matches: [alice, alicia],
            rest: [joan, jo, steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage("A", names, (r) => r.name),
        {
            matches: [alicia, alice],
            rest: [joan, jo, steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage("S", names, (r) => r.name),
        {
            matches: [stephanie, steve],
            rest: [alice, alicia, joan, jo],
        },
    );

    assert.deepEqual(
        typeahead.triage("fred", names, (r) => r.name),
        {
            matches: [],
            rest: [alice, alicia, joan, jo, steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage("Jo", names, (r) => r.name),
        {
            matches: [jo, joan],
            rest: [alice, alicia, steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage("jo", names, (r) => r.name),
        {
            matches: [jo, joan],
            rest: [alice, alicia, steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage(" ", names, (r) => r.name),
        {
            matches: [],
            rest: [alice, alicia, joan, jo, steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage(";", names, (r) => r.name),
        {
            matches: [],
            rest: [alice, alicia, joan, jo, steve, stephanie],
        },
    );
});

function sort_emojis(emojis, query) {
    return typeahead.sort_emojis(emojis, query).map((emoji) => emoji.emoji_name);
}

run_test("sort_emojis: th", () => {
    const emoji_list = [
        {emoji_name: "mother_nature", reaction_type: "realm_emoji"},
        {emoji_name: "thermometer", reaction_type: "realm_emoji"},
        {emoji_name: "thumbs_down", reaction_type: "realm_emoji"},
        {emoji_name: "thumbs_up", reaction_type: "unicode_emoji", emoji_code: "1f44d"},
    ];
    assert.deepEqual(sort_emojis(emoji_list, "th"), [
        "thumbs_up",
        "thermometer",
        "thumbs_down",
        "mother_nature",
    ]);
});

run_test("sort_emojis: sm", () => {
    const emoji_list = [
        {emoji_name: "big_smile", reaction_type: "realm_emoji"},
        {emoji_name: "slight_smile", reaction_type: "unicode_emoji", emoji_code: "1f642"},
        {emoji_name: "small_airplane", reaction_type: "realm_emoji"},
    ];
    assert.deepEqual(sort_emojis(emoji_list, "sm"), [
        "slight_smile",
        "small_airplane",
        "big_smile",
    ]);
});

run_test("sort_emojis: SM", () => {
    const emoji_list = [
        {emoji_name: "big_smile", reaction_type: "realm_emoji"},
        {emoji_name: "slight_smile", reaction_type: "unicode_emoji", emoji_code: "1f642"},
        {emoji_name: "small_airplane", reaction_type: "realm_emoji"},
    ];
    assert.deepEqual(sort_emojis(emoji_list, "SM"), [
        "slight_smile",
        "small_airplane",
        "big_smile",
    ]);
});

run_test("sort_emojis: prefix before midphrase, with underscore (traffic_li)", () => {
    const emoji_list = [
        {emoji_name: "horizontal_traffic_light", reaction_type: "realm_emoji"},
        {emoji_name: "traffic_light", reaction_type: "realm_emoji"},
    ];
    assert.deepEqual(sort_emojis(emoji_list, "traffic_li"), [
        "traffic_light",
        "horizontal_traffic_light",
    ]);
});

run_test("sort_emojis: prefix before midphrase, with space (traffic li)", () => {
    const emoji_list = [
        {emoji_name: "horizontal_traffic_light", reaction_type: "realm_emoji"},
        {emoji_name: "traffic_light", reaction_type: "realm_emoji"},
    ];
    assert.deepEqual(sort_emojis(emoji_list, "traffic li"), [
        "traffic_light",
        "horizontal_traffic_light",
    ]);
});

run_test("sort_emojis: remove duplicates", () => {
    // notice the last 2 are aliases of the same emoji (same emoji code)
    const emoji_list = [
        {emoji_name: "laughter_tears", emoji_code: "1f602", reaction_type: "unicode_emoji"},
        {emoji_name: "tear", emoji_code: "1f972", reaction_type: "unicode_emoji"},
        {emoji_name: "smile_with_tear", emoji_code: "1f972", reaction_type: "unicode_emoji"},
    ];
    assert.deepEqual(typeahead.sort_emojis(emoji_list, "tear"), [emoji_list[1], emoji_list[0]]);
});

run_test("sort_emojis: prioritise realm emojis", () => {
    const emoji_list = [
        {emoji_name: "thank_you", emoji_code: "1f64f", reaction_type: "unicode_emoji"},
        {
            emoji_name: "thank_you_custom",
            url: "something",
            is_realm_emoji: true,
            reaction_type: "realm_emoji",
        },
    ];
    assert.deepEqual(typeahead.sort_emojis(emoji_list, "thank you"), [
        emoji_list[1],
        emoji_list[0],
    ]);
});

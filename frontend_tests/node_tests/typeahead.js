"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("../zjsunit/namespace");
const {run_test} = require("../zjsunit/test");

const typeahead = zrequire("../shared/js/typeahead");

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
    {emoji_name: "japanese_post_office", url: "TBD"},
    {emoji_name: "tada", random_field: "whatever"},
    ...unicode_emojis.map(([emoji_code, emoji_name]) => ({
        emoji_name,
        emoji_code,
    })),
];

function assert_emoji_matches(query, expected) {
    const matcher = typeahead.get_emoji_matcher(query);
    const matches = emojis.filter((emoji) => matcher(emoji));
    assert.deepEqual(matches.map((emoji) => emoji.emoji_name).sort(), expected);
}

run_test("get_emoji_matcher: nonmatches", () => {
    assert_emoji_matches("notaemoji", []);
    assert_emoji_matches("da_", []);
    assert_emoji_matches("da ", []);
});

run_test("get_emoji_matcher: misc matches", () => {
    assert_emoji_matches("da", ["panda_face", "tada"]);
    assert_emoji_matches("panda ", ["panda_face"]);
    assert_emoji_matches("smil", ["big_smile", "smile"]);
    assert_emoji_matches("mile", ["big_smile", "smile"]);

    assert_emoji_matches("japanese_post_", ["japanese_post_office"]);
    assert_emoji_matches("japanese post ", ["japanese_post_office"]);
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

run_test("sort_emojis th", () => {
    const thumbs_up = {
        emoji_name: "thumbs_up",
        emoji_code: "1f44d",
    };
    const thumbs_down = {
        emoji_name: "thumbs_down",
    };
    const thermometer = {
        emoji_name: "thermometer",
    };
    const mother_nature = {
        emoji_name: "mother_nature",
    };

    const emoji_list = [mother_nature, thermometer, thumbs_down, thumbs_up];

    assert.deepEqual(typeahead.sort_emojis(emoji_list, "th"), [
        thumbs_up,
        thermometer,
        thumbs_down,
        mother_nature,
    ]);
});

run_test("sort_emojis sm", () => {
    const big_smile = {
        emoji_name: "big_smile",
    };
    const slight_smile = {
        emoji_name: "slight_smile",
        emoji_code: "1f642",
    };
    const small_airplane = {
        emoji_name: "small_airplane",
    };

    const emoji_list = [big_smile, slight_smile, small_airplane];

    assert.deepEqual(typeahead.sort_emojis(emoji_list, "sm"), [
        slight_smile,
        small_airplane,
        big_smile,
    ]);
});

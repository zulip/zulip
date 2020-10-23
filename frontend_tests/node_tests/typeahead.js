"use strict";

const typeahead = zrequire("typeahead", "shared/js/typeahead");

// The data structures here may be different for
// different apps; the only key thing is we look
// at emoji_name and we'll return the entire structures.

const emoji_japanese_post_office = {
    emoji_name: "japanese_post_office",
    url: "TBD",
};

const emoji_panda_face = {
    emoji_name: "panda_face",
    emoji_code: "1f43c",
};

const emoji_smile = {
    emoji_name: "smile",
};

const emoji_tada = {
    emoji_name: "tada",
    random_field: "whatever",
};

const emojis = [emoji_japanese_post_office, emoji_panda_face, emoji_smile, emoji_tada];

run_test("get_emoji_matcher", () => {
    function assert_matches(query, expected) {
        const matcher = typeahead.get_emoji_matcher(query);
        assert.deepEqual(emojis.filter(matcher), expected);
    }

    assert_matches("notaemoji", []);
    assert_matches("da_", []);
    assert_matches("da ", []);

    assert_matches("da", [emoji_panda_face, emoji_tada]);
    assert_matches("panda ", [emoji_panda_face]);
    assert_matches("smil", [emoji_smile]);
    assert_matches("mile", [emoji_smile]);

    assert_matches("japanese_post_", [emoji_japanese_post_office]);
    assert_matches("japanese post ", [emoji_japanese_post_office]);
});

run_test("triage", () => {
    const alice = {name: "alice"};
    const alicia = {name: "Alicia"};
    const steve = {name: "steve"};
    const stephanie = {name: "Stephanie"};

    const names = [alice, alicia, steve, stephanie];

    assert.deepEqual(
        typeahead.triage("a", names, (r) => r.name),
        {
            matches: [alice, alicia],
            rest: [steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage("A", names, (r) => r.name),
        {
            matches: [alicia, alice],
            rest: [steve, stephanie],
        },
    );

    assert.deepEqual(
        typeahead.triage("S", names, (r) => r.name),
        {
            matches: [stephanie, steve],
            rest: [alice, alicia],
        },
    );

    assert.deepEqual(
        typeahead.triage("fred", names, (r) => r.name),
        {
            matches: [],
            rest: [alice, alicia, steve, stephanie],
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

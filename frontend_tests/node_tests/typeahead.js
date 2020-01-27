const typeahead = zrequire('typeahead', 'shared/js/typeahead');

// The data structures here may be different for
// different apps; the only key thing is we look
// at emoji_name and we'll return the entire structures.

const emoji_japanese_post_office = {
    emoji_name: 'japanese_post_office',
    url: 'TBD',
};

const emoji_panda_face = {
    emoji_name: 'panda_face',
    emoji_code: '1f43c',
};

const emoji_smile = {
    emoji_name: 'smile',
};

const emoji_tada = {
    emoji_name: 'tada',
    random_field: 'whatever',
};

const emojis = [
    emoji_japanese_post_office,
    emoji_panda_face,
    emoji_smile,
    emoji_tada,
];

run_test('get_emoji_matcher', () => {
    function assert_matches(query, expected) {
        const matcher = typeahead.get_emoji_matcher(query);
        assert.deepEqual(
            _.filter(emojis, matcher),
            expected
        );
    }

    assert_matches('notaemoji', []);
    assert_matches('da_', []);
    assert_matches('da ', []);

    assert_matches('da', [emoji_panda_face, emoji_tada]);
    assert_matches('panda ', [emoji_panda_face]);
    assert_matches('smil', [emoji_smile]);
    assert_matches('mile', [emoji_smile]);

    assert_matches(
        'japanese_post_', [emoji_japanese_post_office]);
    assert_matches(
        'japanese post ', [emoji_japanese_post_office]);
});

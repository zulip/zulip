set_global('$', global.make_zjquery());
set_global('page_params', {
    emojiset: 'google',
});
set_global('upload_widget', {});

zrequire('emoji_codes', 'generated/emoji/emoji_codes');
zrequire('emoji');
zrequire('markdown');
zrequire('util');

(function test_build_emoji_upload_widget() {
    var build_widget_stub = false;
    upload_widget.build_widget = function (
        get_file_input,
        file_name_field,
        input_error,
        clear_button,
        upload_button
    ) {
        assert.deepEqual(get_file_input(), $('#emoji_file_input'));
        assert.deepEqual(file_name_field, $('#emoji-file-name'));
        assert.deepEqual(input_error, $('#emoji_file_input_error'));
        assert.deepEqual(clear_button, $('#emoji_image_clear_button'));
        assert.deepEqual(upload_button, $('#emoji_upload_button'));
        build_widget_stub = true;
    };
    emoji.build_emoji_upload_widget();
    assert(build_widget_stub);
}());

(function test_initialize() {
    var image_stub = false;
    class Image {
        set src(data) {
            assert.equal(data, '/static/generated/emoji/sheet_google_64.png');
            image_stub = true;
        }
    }
    set_global('Image', Image);
    emoji.initialize();
    assert(image_stub);
}());

(function test_get_canonical_name() {
    emoji.active_realm_emojis = {
        realm_emoji: 'TBD',
    };
    var canonical_name = emoji.get_canonical_name('realm_emoji');
    assert.equal(canonical_name, 'realm_emoji');

    global.emoji_codes = {
        name_to_codepoint: {
            '+1': '1f44d',
        },
        codepoint_to_name: {
            '1f44d': 'thumbs_up',
        },
    };
    canonical_name = emoji.get_canonical_name('+1');
    assert.equal(canonical_name, 'thumbs_up');

    emoji.active_realm_emojis = {
        '+1': 'TBD',
    };
    canonical_name = emoji.get_canonical_name('+1');
    assert.equal(canonical_name, '+1');

    var errored = false;
    set_global('blueslip', {
        error: function (error) {
            assert.equal(error, "Invalid emoji name: non_existent");
            errored = true;
        },
    });
    emoji.get_canonical_name('non_existent');
    assert(errored);
}());

(function test_translate_emoticons_to_names() {
    // Simple test
    var test_text = 'Testing :)';
    var expected = 'Testing :smiley:';
    var result = emoji.translate_emoticons_to_names(test_text);
    assert.equal(expected, result);

    // Extensive tests.
    // The following code loops over the test cases and each emoticon conversion
    // to generate multiple test cases.
    var testcases = [
        {name: 'only emoticon', original: '<original>', expected: '<converted>'},
        {name: 'space at start', original: ' <original>', expected: ' <converted>'},
        {name: 'space at end', original: '<original> ', expected: '<converted> '},
        {name: 'symbol at end', original: '<original>!', expected: '<converted>!'},
        {name: 'symbol at start', original: 'Hello,<original>', expected: 'Hello,<converted>'},
        {name: 'after a word', original: 'Hello<original>', expected: 'Hello<original>'},
        {name: 'between words', original: 'Hello<original>World', expected: 'Hello<original>World'},
        {name: 'end of sentence', original: 'End of sentence. <original>', expected: 'End of sentence. <converted>'},
        {name: 'between symbols', original: 'Hello.<original>! World.', expected: 'Hello.<original>! World.'},
        {name: 'before end of sentence', original: 'Hello <original>!', expected: 'Hello <converted>!'},
    ];
    Object.keys(emoji.EMOTICON_CONVERSIONS).forEach(key => {
        testcases.forEach(t => {
            var converted_value = `:${emoji.EMOTICON_CONVERSIONS[key]}:`;
            t = Object.assign({}, t); // circumvent copy by reference.
            t.original = t.original.replace(/(<original>)/g, key);
            t.expected = t.expected.replace(/(<original>)/g, key);
            t.expected = t.expected.replace(/(<converted>)/g, converted_value);
            var result = emoji.translate_emoticons_to_names(t.original);
            assert.equal(result, t.expected);
        });
    });
}());

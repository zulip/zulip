set_global('$', global.make_zjquery());
set_global('page_params', {
    emojiset: 'google',
});
set_global('upload_widget', {});
set_global('blueslip', global.make_zblueslip());

zrequire('emoji_codes', 'generated/emoji/emoji_codes');
zrequire('emoji');
zrequire('markdown');
zrequire('util');

run_test('build_emoji_upload_widget', () => {
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
});

run_test('initialize', () => {
    var image_stub = false;
    var urls = [];
    var calls = 0;
    class Image {
        set src(data) {
            image_stub = true;
            urls.push(data);
            calls += 1;
        }
    }
    set_global('Image', Image);
    emoji.initialize();
    assert(image_stub);
    assert.equal(calls, 2);
    assert.deepEqual(urls, ['/static/generated/emoji/sheet-google-64.png',
                            '/static/generated/emoji/images-google-64/1f419.png']);

    // Check initialization sequence for `text` emojiset.
    page_params.emojiset = 'text';
    image_stub = false;
    urls = [];
    calls = 0;
    emoji.initialize();
    assert(image_stub);
    assert.equal(calls, 2);
    assert.deepEqual(urls, ['/static/generated/emoji/sheet-google-blob-64.png',
                            '/static/generated/emoji/images-google-blob-64/1f419.png']);
});

run_test('get_canonical_name', () => {
    emoji.active_realm_emojis = {
        realm_emoji: 'TBD',
    };
    var canonical_name = emoji.get_canonical_name('realm_emoji');
    assert.equal(canonical_name, 'realm_emoji');

    var orig_emoji_codes = global.emoji_codes;
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

    blueslip.set_test_data('error', 'Invalid emoji name: non_existent');
    emoji.get_canonical_name('non_existent');
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();
    global.emoji_codes = orig_emoji_codes;
});

run_test('translate_emoticons_to_names', () => {
    // Simple test
    var test_text = 'Testing :)';
    var expected = 'Testing :slight_smile:';
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
    _.each(emoji_codes.emoticon_conversions, (full_name, shortcut) => {
        _.each(testcases, (t) => {
            var converted_value = full_name;
            var original = t.original;
            var expected = t.expected;
            original = original.replace(/(<original>)/g, shortcut);
            expected = expected.replace(/(<original>)/g, shortcut)
                .replace(/(<converted>)/g, converted_value);
            var result = emoji.translate_emoticons_to_names(original);
            assert.equal(result, expected);
        });
    });
});

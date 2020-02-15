set_global('$', global.make_zjquery());
set_global('page_params', {
    emojiset: 'google',
    realm_emoji: {},
});
set_global('upload_widget', {});
set_global('blueslip', global.make_zblueslip());

zrequire('emoji');
zrequire('markdown');

run_test('build_emoji_upload_widget', () => {
    let build_widget_stub = false;
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
    let image_stub = false;
    let urls = [];
    let calls = 0;
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
    emoji.active_realm_emojis = new Map(Object.entries({
        realm_emoji: 'TBD',
    }));
    let canonical_name = emoji.get_canonical_name('realm_emoji');
    assert.equal(canonical_name, 'realm_emoji');

    canonical_name = emoji.get_canonical_name('thumbs_up');
    assert.equal(canonical_name, '+1');

    canonical_name = emoji.get_canonical_name('+1');
    assert.equal(canonical_name, '+1');

    canonical_name = emoji.get_canonical_name('airplane');
    assert.equal(canonical_name, 'airplane');

    blueslip.set_test_data('error', 'Invalid emoji name: non_existent');
    emoji.get_canonical_name('non_existent');
    assert.equal(blueslip.get_test_logs('error').length, 1);
    blueslip.clear_test_data();
});

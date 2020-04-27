set_global('$', global.make_zjquery());
set_global('page_params', {
    emojiset: 'google',
    realm_emoji: {},
});
set_global('upload_widget', {});

zrequire('emoji');
zrequire('settings_emoji');

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
    settings_emoji.build_emoji_upload_widget();
    assert(build_widget_stub);
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

    blueslip.expect('error', 'Invalid emoji name: non_existent');
    emoji.get_canonical_name('non_existent');
});

function set_up_spain_realm_emoji_for_test() {
    const realm_emojis = {
        101: {
            id: 101,
            name: 'spain',
            source_url: '/some/path/to/spain.png',
            deactivated: false,
        },
    };
    emoji.update_emojis(realm_emojis);
}

run_test('get_emoji_* API', () => {
    assert.equal(emoji.get_emoji_name('1f384'), 'holiday_tree');
    assert.equal(emoji.get_emoji_name('1f951'), 'avocado');
    assert.equal(emoji.get_emoji_name('bogus'), undefined);

    assert.equal(emoji.get_emoji_codepoint('avocado'), '1f951');
    assert.equal(emoji.get_emoji_codepoint('holiday_tree'), '1f384');
    assert.equal(emoji.get_emoji_codepoint('bogus'), undefined);

    assert.equal(emoji.get_realm_emoji_url('spain'), undefined);
    set_up_spain_realm_emoji_for_test();
    assert.equal(emoji.get_realm_emoji_url('spain'), '/some/path/to/spain.png');
});

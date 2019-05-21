zrequire('lightbox');

set_global('blueslip', global.make_zblueslip());
set_global('message_store', {
    get: () => ({}),
});
set_global('Image', class Image {});
set_global('overlays', {
    close_overlay: () => {},
    close_active: () => {},
    open_overlay: () => {},
});
set_global('popovers', {
    hide_all: () => {},
});

set_global('$', global.make_zjquery());

run_test('pan_and_zoom', () => {
    $.clear_all_elements();

    var img = '<img src="./image.png" data-src-fullsize="./original.png">';
    var link = '<a href="https://zulip.com"></a>';
    var msg = '<div [zid]></div>';
    $(img).set_parent($(link));
    $(link).set_parent($(msg));

    // Used by render_lightbox_list_images
    $.stub_selector('.focused_table .message_inline_image img', []);

    lightbox.open(img);
    assert.equal(blueslip.get_test_logs('error').length, 0);
    lightbox.open('<img src="./image.png">');
    assert.equal(blueslip.get_test_logs('error').length, 0);
});

run_test('open_url', () => {
    $.clear_all_elements();

    var url = 'https://youtube.com/1234';
    var img = '<img></img>';
    $(img).attr('src', "https://youtube.com/image.png");
    var link = '<a></a>';
    $(link).attr('href', url);
    var div = '<div class="youtube-video"></div>';
    var msg = '<div [zid]></div>';
    $(img).set_parent($(link));
    $(link).set_parent($(div));
    $(div).set_parent($(msg));

    // Used by render_lightbox_list_images
    $.stub_selector('.focused_table .message_inline_image img', []);

    lightbox.open(img);
    assert.equal($('.image-actions .open').attr('href'), url);
    assert.equal(blueslip.get_test_logs('error').length, 0);
});

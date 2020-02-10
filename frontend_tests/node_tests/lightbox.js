zrequire('lightbox');

set_global('blueslip', global.make_zblueslip());

const _message_store = new Map();
_message_store.set(1234, { sender_full_name: "Test User" });

set_global('message_store', _message_store);
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

    const img = '<img src="./image.png" data-src-fullsize="./original.png">';
    const link = '<a href="https://zulip.com"></a>';

    /* Due to how zquery works, we have to use a literal [zid] in the element,
       since that's what the code looks for and we have to manually set the attr
       that should be returned from the store. */
    const msg = $('<div [zid]></div>');
    msg.attr("zid", "1234");
    $(img).set_parent($(link));
    $(link).set_parent(msg);

    // Used by render_lightbox_list_images
    $.stub_selector('.focused_table .message_inline_image img', []);

    lightbox.open(img);
    assert.equal(blueslip.get_test_logs('error').length, 0);
    lightbox.open('<img src="./image.png">');
    assert.equal(blueslip.get_test_logs('error').length, 0);
});

run_test('open_url', () => {
    $.clear_all_elements();

    const url = 'https://youtube.com/1234';
    const img = '<img></img>';
    $(img).attr('src', "https://youtube.com/image.png");
    const link = '<a></a>';
    $(link).attr('href', url);
    const div = '<div class="youtube-video"></div>';
    /* Due to how zquery works, we have to use a literal [zid] in the element,
       since that's what the code looks for and we have to manually set the attr
       that should be returned from the store. */
    const msg = $('<div [zid]></div>');
    msg.attr("zid", "1234");
    $(img).set_parent($(link));
    $(link).set_parent($(div));
    $(div).set_parent(msg);

    // Used by render_lightbox_list_images
    $.stub_selector('.focused_table .message_inline_image img', []);

    lightbox.open(img);
    assert.equal($('.image-actions .open').attr('href'), url);
    assert.equal(blueslip.get_test_logs('error').length, 0);
});

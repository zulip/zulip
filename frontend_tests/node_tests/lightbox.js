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
set_global('$', function () {
    return {
        hasClass: () => false,
        closest: () => [],
        attr: (attr) => attr,
        parent: () => ({
            closest: () => ({
                attr: (attr) => attr,
            }),
            attr: (attr) => attr,
        }),
        html: () => ({
            show: () => {},
        }),
        hide: () => {},
        show: () => {},
        text: () => '',
    };
});

run_test('pan_and_zoom', () => {
    lightbox.open('<img src="./image.png" data-src-fullsize="./original.png">');
    assert.equal(blueslip.get_test_logs('error').length, 0);
    lightbox.open('<img src="./image.png">');
    assert.equal(blueslip.get_test_logs('error').length, 0);
});

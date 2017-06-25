set_global('$', global.make_zjquery());
set_global('page_params', {});
set_global('upload_widget', {});

add_dependencies({
    emoji_codes: 'generated/emoji/emoji_codes.js',
});

var emoji = require('js/emoji.js');

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
            assert.equal(data, '/static/generated/emoji/sheet_google_32.png');
            image_stub = true;
        }
    }
    set_global('Image', Image);
    emoji.initialize();
    assert(image_stub);
}());

set_global('$', global.make_zjquery());
set_global('document', {
    location: { },
});
set_global('i18n', global.stub_i18n);
set_global('page_params', { });
set_global('csrf_token', { });

// Setting these up so that we can test that links to uploads within messages are
// automatically converted to server relative links.
global.document.location.protocol = 'https:';
global.document.location.host = 'foo.com';

zrequire('compose_ui');
zrequire('compose_state');
zrequire('compose');
zrequire('upload');

(function test_upload_started() {
    $("#compose-send-button").prop('disabled', false);
    $("#compose-send-status").removeClass("alert-info").hide();
    $(".compose-send-status-close").one = function (ev_name, handler) {
        assert.equal(ev_name, 'click');
        assert(handler);
    };
    $("#error-msg").html('');
    var test_html = '<div class="progress progress-striped active">' +
                    '<div class="bar" id="upload-bar" style="width: 00%;">' +
                    '</div></div>';
    $("<p>").after = function (html) {
        assert.equal(html, test_html);
        return 'fake-html';
    };

    upload.uploadStarted();

    assert.equal($("#compose-send-button").attr("disabled"), '');
    assert($("#compose-send-status").hasClass("alert-info"));
    assert($("#compose-send-status").visible());
    assert.equal($("<p>").text(), 'translated: Uploading…');
    assert.equal($("#error-msg").html(), 'fake-html');
}());

(function test_progress_updated() {
    var width_update_checked = false;
    $("#upload-bar").width = function (width_percent) {
        assert.equal(width_percent, '39%');
        width_update_checked = true;
    };
    upload.progressUpdated(1, '', 39);
    assert(width_update_checked);
}());

(function test_upload_error() {
    function setup_test() {
        $("#compose-send-status").removeClass("alert-error");
        $("#compose-send-status").addClass("alert-info");
        $("#compose-send-button").attr("disabled", 'disabled');
        $("#error-msg").text('');
    }

    function assert_side_effects(msg, check_html=false) {
        assert($("#compose-send-status").hasClass("alert-error"));
        assert(!$("#compose-send-status").hasClass("alert-info"));
        assert.equal($("#compose-send-button").prop("disabled"), false);
        if (check_html) {
            assert.equal($("#error-msg").html(), msg);
        } else {
            assert.equal($("#error-msg").text(), msg);
        }
    }

    function test(err, file, msg) {
        setup_test();
        upload.uploadError(err, file);
        // The text function and html function in zjquery is not in sync
        // with each other. QuotaExceeded changes html while all other errors
        // changes body.
        if (err === 'QuotaExceeded') {
            assert_side_effects(msg, true);
        } else {
            assert_side_effects(msg);
        }
    }

    var msg_prefix = 'translated: ';
    var msg_1 = 'File upload is not yet available for your browser.';
    var msg_2 = 'Unable to upload that many files at once.';
    var msg_3 = '"foobar.txt" was too large; the maximum file size is 25MiB.';
    var msg_4 = 'Sorry, the file was too large.';
    var msg_5 = 'Upload would exceed your maximum quota. You can delete old attachments to ' +
                'free up space. <a href="#settings/uploaded-files">translated: Click here</a>';

    var msg_6 = 'An unknown error occurred.';

    test('BrowserNotSupported', {}, msg_prefix + msg_1);
    test('TooManyFiles', {}, msg_prefix + msg_2);
    test('FileTooLarge', {name: 'foobar.txt'}, msg_prefix + msg_3);
    test('REQUEST ENTITY TOO LARGE', {}, msg_prefix + msg_4);
    test('QuotaExceeded', {}, msg_prefix + msg_5);
    test('Do-not-match-any-case', {}, msg_prefix + msg_6);
}());

(function test_upload_finish() {
    function test(i, response, textbox_val) {
        var compose_ui_autosize_textarea_checked = false;
        var compose_actions_start_checked = false;

        function setup() {
            $("#new_message_content").val('');
            compose_ui.autosize_textarea = function () {
                compose_ui_autosize_textarea_checked = true;
            };
            compose_state.set_message_type();
            global.compose_actions = {
                start: function (msg_type) {
                    assert.equal(msg_type, 'stream');
                    compose_actions_start_checked = true;
                },
            };
            $("#compose-send-button").attr('disabled', 'disabled');
            $("#compose-send-status").addClass("alert-info");
            $("#compose-send-status").show();
            $('#file_input').clone = function (param) {
                assert(param);
                return $('#file_input');
            };
        }

        function assert_side_effects() {
            assert.equal($("#new_message_content").val(), textbox_val);
            if (response.uri) {
                assert(compose_actions_start_checked);
                assert(compose_ui_autosize_textarea_checked);
                assert.equal($("#compose-send-button").prop('disabled'), false);
                assert(!$('#compose-send-status').hasClass('alert-info'));
                assert(!$('#compose-send-status').visible());
            }
        }

        setup();
        upload.uploadFinished(i, {}, response);
        assert_side_effects();
    }

    var msg_1 = '[pasted image](https://foo.com/uploads/122456) ';
    var msg_2 = '[foobar.jpeg](https://foo.com/user_uploads/foobar.jpeg) ';

    test(-1, {}, '');
    test(-1, {uri: 'https://foo.com/uploads/122456'}, msg_1);
    test(1, {uri: '/user_uploads/foobar.jpeg'}, msg_2);
}());

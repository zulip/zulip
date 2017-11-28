var upload = (function () {

var exports = {};

function make_upload_absolute(uri) {
    if (uri.indexOf(compose.uploads_path) === 0) {
        // Rewrite the URI to a usable link
        return compose.uploads_domain + uri;
    }
    return uri;
}

// This function resets an input type="file".  Pass in the
// jquery object.
function clear_out_file_list(jq_file_list) {
    if (compose.clone_file_input !== undefined) {
        jq_file_list.replaceWith(compose.clone_file_input.clone(true));
    }
    // Hack explanation:
    // IE won't let you do this (untested, but so says StackOverflow):
    //    $("#file_input").val("");
}

exports.options = function (config) {
    var textarea;
    var send_button;
    var send_status;
    var send_status_close;
    var error_msg;
    var upload_bar;
    var file_input;

    switch (config.mode) {
        case 'compose':
            textarea = $('#compose-textarea');
            send_button = $('#compose-send-button');
            send_status = $('#compose-send-status');
            send_status_close = $('.compose-send-status-close');
            error_msg = $('#compose-error-msg');
            upload_bar = 'compose-upload-bar';
            break;
        case 'edit':
            textarea = $('#message_edit_content_' + config.row);
            send_button = textarea.closest('.message_edit_save');
            send_status = $('#message-edit-send-status-' + config.row);
            send_status_close = send_status.find('.send-status-close');
            error_msg = send_status.find('.error-msg');
            upload_bar = 'message-edit-upload-bar-' + config.row;
            break;
        default:
            throw Error('Unreachable!');
    }

    var uploadStarted = function () {
        send_button.attr("disabled", "");
        send_status.addClass("alert-info").show();
        send_status_close.one('click', compose.abort_xhr);
        error_msg.html($("<p>")
                 .text(i18n.t("Uploading…"))
                 .after('<div class="progress progress-striped active">' +
                        '<div class="bar" id="' + upload_bar + '" style="width: 00%;"></div>' +
                        '</div>'));
    };

    var progressUpdated = function (i, file, progress) {
        $('#' + upload_bar).width(progress + "%");
    };

    var uploadError = function (err, file) {
        var msg;
        send_status.addClass("alert-error")
            .removeClass("alert-info");
        send_button.prop("disabled", false);

        switch (err) {
            case 'BrowserNotSupported':
                msg = i18n.t("File upload is not yet available for your browser.");
                break;
            case 'TooManyFiles':
                msg = i18n.t("Unable to upload that many files at once.");
                break;
            case 'FileTooLarge':
                // sanitization not needed as the file name is not potentially parsed as HTML, etc.
                var context = {
                    file_name: file.name,
                };
                msg = i18n.t('"__file_name__" was too large; the maximum file size is 25MiB.', context);
                break;
            case 'REQUEST ENTITY TOO LARGE':
                msg = i18n.t("Sorry, the file was too large.");
                break;
            case 'QuotaExceeded':
                var translation_part1 = i18n.t(
                    'Upload would exceed your maximum quota. You can delete old attachments to free up space.');
                var translation_part2 = i18n.t('Click here');
                msg = translation_part1 + ' <a href="#settings/uploaded-files">' + translation_part2 + '</a>';
                error_msg.html(msg);
                return;
            default:
                msg = i18n.t("An unknown error occurred.");
                break;
        }
        error_msg.text(msg);
    };

    var uploadFinished = function (i, file, response) {
        if (response.uri === undefined) {
            return;
        }
        var split_uri = response.uri.split("/");
        var filename = split_uri[split_uri.length - 1];
        // Urgh, yet another hack to make sure we're "composing"
        // when text gets added into the composebox.
        if (!compose_state.composing()) {
            compose_actions.start('stream');
        }

        var uri = make_upload_absolute(response.uri);

        if (i === -1) {
            // This is a paste, so there's no filename. Show the image directly
            textarea.val(textarea.val() + "[pasted image](" + uri + ") ");
        } else {
            // This is a dropped file, so make the filename a link to the image
            textarea.val(textarea.val() + "[" + filename + "](" + uri + ")" + " ");
        }
        compose_ui.autosize_textarea();
        send_button.prop("disabled", false);
        send_status.removeClass("alert-info").hide();

        // In order to upload the same file twice in a row, we need to clear out
        // the #file_input element, so that the next time we use the file dialog,
        // an actual change event is fired.  This is extracted to a function
        // to abstract away some IE hacks.
        clear_out_file_list($("#file_input"));
    };

    return {
        url: "/json/user_uploads",
        fallback_id: "file_input",
        paramname: "file",
        maxfilesize: page_params.maxfilesize,
        data: {
            // the token isn't automatically included in filedrop's post
            csrfmiddlewaretoken: csrf_token,
        },
        raw_droppable: ['text/uri-list', 'text/plain'],
        drop: uploadStarted,
        progressUpdated: progressUpdated,
        error: uploadError,
        uploadFinished: uploadFinished,
        rawDrop: function (contents) {
            if (!compose_state.composing()) {
                compose_actions.start('stream');
            }
            textarea.val(textarea.val() + contents);
            compose_ui.autosize_textarea();
        },
    };
};

// Expose the internal file upload functions to the desktop app,
// since the linux/windows QtWebkit based apps upload images
// directly to the server
if (window.bridge) {
    var opts = exports.options({ mode: "compose" });

    exports.uploadStarted = opts.drop;
    exports.progressUpdated = opts.progressUpdated;
    exports.uploadError = opts.error;
    exports.uploadFinished = opts.uploadFinished;
}

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = upload;
}

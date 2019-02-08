var upload = (function () {

var exports = {};

function make_upload_absolute(uri) {
    if (uri.indexOf(compose.uploads_path) === 0) {
        // Rewrite the URI to a usable link
        return compose.uploads_domain + uri;
    }
    return uri;
}

// Show the upload button only if the browser supports it.
exports.feature_check = function (upload_button) {
    if (window.XMLHttpRequest && (new XMLHttpRequest()).upload) {
        upload_button.removeClass("notdisplayed");
    }
};

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
        file_input = 'file_input';
        break;
    case 'edit':
        textarea = $('#message_edit_content_' + config.row);
        send_button = textarea.closest('.message_edit_save');
        send_status = $('#message-edit-send-status-' + config.row);
        send_status_close = send_status.find('.send-status-close');
        error_msg = send_status.find('.error-msg');
        upload_bar = 'message-edit-upload-bar-' + config.row;
        file_input = 'message_edit_file_input_' + config.row;
        break;
    default:
        throw Error("Invalid upload mode!");
    }

    var hide_upload_status = function () {
        send_button.prop("disabled", false);
        send_status.removeClass("alert-info").hide();
        $('div.progress.active').remove();
    };

    var drop = function () {
        send_button.attr("disabled", "");
        send_status.addClass("alert-info").show();
        send_status_close.one('click', function () {
            setTimeout(function () {
                hide_upload_status();
            }, 500);
            compose.abort_xhr();
        });
    };

    var uploadStarted = function (i, file) {
        error_msg.html($("<p>").text(i18n.t("Uploading…")));
        // Here file.lastModified is unique for each upload
        // so it is used to track each upload individually
        send_status.append('<div class="progress active">' +
                           '<div class="bar" id="' + upload_bar + '-' + file.lastModified + '" style="width: 0"></div>' +
                           '</div>');
        compose_ui.insert_syntax_and_focus("[Uploading " + file.name + "…]()", textarea);
    };

    var progressUpdated = function (i, file, progress) {
        $("#" + upload_bar + '-' + file.lastModified).width(progress + "%");
    };

    var uploadError = function (error_code, server_response, file) {
        var msg;
        send_status.addClass("alert-error").removeClass("alert-info");
        send_button.prop("disabled", false);
        if (file !== undefined) {
            $("#" + upload_bar + '-' + file.lastModified).parent().remove();
        }

        switch (error_code) {
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
        case 413: // HTTP status "Request Entity Too Large"
            msg = i18n.t("Sorry, the file was too large.");
            break;
        case 400:
            var server_message = server_response && server_response.msg;
            msg = server_message || i18n.t("An unknown error occurred.");
            break;
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
        if (config.mode === 'compose' && !compose_state.composing()) {
            compose_actions.start('stream');
        } else if (config.mode === 'edit' && document.activeElement !== textarea) {
            // If we are editing, focus on the edit message box
            textarea.focus();
        }

        var uri = make_upload_absolute(response.uri);

        if (i === -1) {
            // This is a paste, so there's no filename. Show the image directly
            var pasted_image_uri = "[pasted image](" + uri + ")";
            compose_ui.replace_syntax("[Uploading " + file.name + "…]()", pasted_image_uri, textarea);
        } else {
            // This is a dropped file, so make the filename a link to the image
            var filename_uri = "[" + filename + "](" + uri + ")";
            compose_ui.replace_syntax("[Uploading " + file.name + "…]()", filename_uri, textarea);
        }
        compose_ui.autosize_textarea();

        setTimeout(function () {
            $("#" + upload_bar  + '-' + file.lastModified).parent().remove();
            if ($('div.progress.active').length === 0) {
                hide_upload_status(file);
            }
        }, 500);

        // In order to upload the same file twice in a row, we need to clear out
        // the file input element, so that the next time we use the file dialog,
        // an actual change event is fired. IE doesn't allow .val('') so we
        // need to clone it. (Taken from the jQuery form plugin)
        if (/MSIE/.test(navigator.userAgent)) {
            $('#' + file_input).replaceWith($('#' + file_input).clone(true));
        } else {
            $('#' + file_input).val('');
        }
    };

    return {
        url: "/json/user_uploads",
        fallback_id: file_input,  // Target for standard file dialog
        paramname: "file",
        maxfilesize: page_params.maxfilesize,
        data: {
            // the token isn't automatically included in filedrop's post
            csrfmiddlewaretoken: csrf_token,
        },
        raw_droppable: ['text/uri-list', 'text/plain'],
        drop: drop,
        uploadStarted: uploadStarted,
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

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = upload;
}
window.upload = upload;

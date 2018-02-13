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

exports.options = function () {
    var uploadStarted = function () {
        $("#compose-send-button").attr("disabled", "");
        $("#compose-send-status").addClass("alert-info").show();
        $(".compose-send-status-close").one('click', compose.abort_xhr);
        $("#compose-error-msg").html($("<p>").text(i18n.t("Uploading…"))
            .after('<div class="progress progress-striped active">' +
                   '<div class="bar" id="compose-upload-bar" style="width: 00%;"></div>' +
                   '</div>'));
    };

    var progressUpdated = function (i, file, progress) {
        $("#compose-upload-bar").width(progress + "%");
    };

    var uploadError = function (error_code, server_response, file) {
        var msg;
        $("#compose-send-status").addClass("alert-error")
            .removeClass("alert-info");
        $("#compose-send-button").prop("disabled", false);
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
        $("#compose-error-msg").text(msg);
    };

    var uploadFinished = function (i, file, response) {
        if (response.uri === undefined) {
            return;
        }
        var textbox = $("#compose-textarea");
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
            textbox.val(textbox.val() + "[pasted image](" + uri + ") ");
        } else {
            // This is a dropped file, so make the filename a link to the image
            textbox.val(textbox.val() + "[" + filename + "](" + uri + ")" + " ");
        }
        compose_ui.autosize_textarea();
        $("#compose-send-button").prop("disabled", false);
        $("#compose-send-status").removeClass("alert-info").hide();

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
            var textbox = $("#compose-textarea");
            if (!compose_state.composing()) {
                compose_actions.start('stream');
            }
            textbox.val(textbox.val() + contents);
            compose_ui.autosize_textarea();
        },
    };
};

exports.initialize = function () {
    $("#compose").filedrop(
        exports.options()
    );
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = upload;
}

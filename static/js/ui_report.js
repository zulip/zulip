"use strict";

const _ = require("lodash");
/* Arguments used in the report_* functions are,
   response- response that we want to display
   status_box- element being used to display the response
   cls- class that we want to add/remove to/from the status_box
*/

exports.message = function (response, status_box, cls, remove_after) {
    if (cls === undefined) {
        cls = "alert";
    }

    // Note we use html() below, since we can rely on our callers escaping HTML
    // via i18n.t when interpolating data.
    status_box
        .removeClass(common.status_classes)
        .addClass(cls)
        .html(response)
        .stop(true)
        .fadeTo(0, 1);
    if (remove_after) {
        setTimeout(() => {
            status_box.fadeOut(400);
        }, remove_after);
    }
    status_box.addClass("show");
};

exports.error = function (response, xhr, status_box, remove_after) {
    if (xhr && xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        const server_response = _.escape(JSON.parse(xhr.responseText).msg);
        if (response) {
            response += ": " + server_response;
        } else {
            response = server_response;
        }
    }

    exports.message(response, status_box, "alert-error", remove_after);
};

exports.client_error = function (response, status_box, remove_after) {
    exports.message(response, status_box, "alert-error", remove_after);
};

exports.success = function (response, status_box, remove_after) {
    exports.message(response, status_box, "alert-success", remove_after);
};

exports.generic_embed_error = function (error) {
    const $alert = $("<div class='alert home-error-bar'></div>");
    const $exit = "<div class='exit'></div>";

    $(".alert-box").append(
        $alert.html($exit + "<div class='content'>" + error + "</div>").addClass("show"),
    );
};

exports.generic_row_button_error = function (xhr, btn) {
    if (xhr.status.toString().charAt(0) === "4") {
        btn.closest("td").html(
            $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg),
        );
    } else {
        btn.text(i18n.t("Failed!"));
    }
};

exports.hide_error = function ($target) {
    $target.addClass("fade-out");
    setTimeout(() => {
        $target.removeClass("show fade-out");
    }, 300);
};

exports.show_error = function ($target) {
    $target.addClass("show");
};

window.ui_report = exports;

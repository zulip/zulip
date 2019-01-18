var ui_report = (function () {

var exports = {};

/* Arguments used in the report_* functions are,
   response- response that we want to display
   status_box- element being used to display the response
   cls- class that we want to add/remove to/from the status_box
*/

exports.message = function (response, status_box, cls, remove_after) {
    if (cls === undefined) {
        cls = 'alert';
    }

    // Note we use html() below, since we can rely on our callers escaping HTML
    // via i18n.t when interpolating data.
    status_box.removeClass(common.status_classes).addClass(cls)
        .html(response).stop(true).fadeTo(0, 1);
    if (remove_after) {
        setTimeout(function () {
            status_box.fadeTo(200, 0);
        }, remove_after);
    }
    status_box.addClass("show");
};

function escape(html) {
    return html
        .toString()
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

exports.error = function (response, xhr, status_box) {
    if (xhr && xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        var server_response = escape(JSON.parse(xhr.responseText).msg);
        if (response) {
            response += ": " + server_response;
        } else {
            response = server_response;
        }
    }

    exports.message(response, status_box, 'alert-error');
};

exports.success = function (response, status_box, remove_after) {
    exports.message(response, status_box, 'alert-success', remove_after);
};

exports.generic_embed_error = function (error) {
    var $alert = $("<div class='alert home-error-bar'></div>");
    var $exit = "<div class='exit'></div>";

    $(".alert-box").append($alert.html($exit + "<div class='content'>" + error + "</div>").addClass("show"));
};

exports.generic_row_button_error = function (xhr, btn) {
    if (xhr.status.toString().charAt(0) === "4") {
        btn.closest("td").html(
            $("<p>").addClass("text-error").text(JSON.parse(xhr.responseText).msg)
        );
    } else {
        btn.text(i18n.t("Failed!"));
    }
};

exports.hide_error = function ($target) {
    $target.addClass("fade-out");
    setTimeout(function () {
        $target.removeClass("show fade-out");
    }, 300);
};

exports.show_error = function ($target) {
    $target.addClass("show");
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = ui_report;
}
window.ui_report = ui_report;

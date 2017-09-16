var ui_report = (function () {

var exports = {};

/* Arguments used in the report_* functions are,
   response- response that we want to display
   status_box- element being used to display the response
   cls- class that we want to add/remove to/from the status_box
   type- used to define more complex logic for special cases (currently being
         used only for subscriptions-status) */

exports.message = function (response, status_box, cls, type) {
    if (cls === undefined) {
        cls = 'alert';
    }

    if (type === undefined) {
        type = ' ';
    }

    if (type === 'subscriptions-status') {
        status_box.removeClass(common.status_classes).addClass(cls).children('#response')
              .text(response).stop(true).fadeTo(0, 1);
    } else {
        status_box.removeClass(common.status_classes).addClass(cls)
              .text(response).stop(true).fadeTo(0, 1);
    }

    status_box.addClass("show");
};

exports.error = function (response, xhr, status_box, type) {
    if (xhr && xhr.status.toString().charAt(0) === "4") {
        // Only display the error response for 4XX, where we've crafted
        // a nice response.
        response += ": " + JSON.parse(xhr.responseText).msg;
    }

    exports.message(response, status_box, 'alert-error', type);
};

exports.success = function (response, status_box, type) {
    exports.message(response, status_box, 'alert-success', type);
};

exports.generic_embed_error = function (error) {
    var $alert = $("<div class='alert home-error-bar'></div>");
    var $exit = "<div class='exit'></div>";

    $(".alert-box").append($alert.html($exit + "<div class='content'>" + error + "</div>").addClass("show"));
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

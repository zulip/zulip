var desktop_notifications_panel = (function () {

var exports = {};

var resize_app = function () {
    var panels_height = $("#panels").height();
    $("body > .app").height("calc(100% - " + panels_height + "px)");
};

var show_step = function (step) {
    $("#panels [data-step]").hide().filter("[data-step=" + step + "]").show();
};

var get_step = function () {
    return $("#panels [data-step]").filter(":visible").data("step");
};

exports.initialize = function () {
    var ls = localstorage();

    var should_show_notifications = (
        // if the user said to never show banner on this computer again, it will
        // be stored as `true` so we want to negate that.
        !ls.get("dontAskForNotifications") &&
        !notifications.granted_desktop_notifications_permission()
    );

    if (should_show_notifications) {
        $("#desktop-notifications-panel").show();
        resize_app();
    }

    $(".request-desktop-notifications").on("click", function (e) {
        e.preventDefault();
        $(this).closest(".alert").hide();
        notifications.request_desktop_notifications_permission();
        resize_app();
    });

    $(".reject-notifications").on("click", function () {
        $(this).closest(".alert").hide();
        ls.set("dontAskForNotifications", true);
        resize_app();
    });

    $("#panels").on("click", ".alert .close, .alert .exit", function (e) {
        e.stopPropagation();
        if (get_step() === 1) {
            show_step(2);
        } else {
            $(this).closest(".alert").hide();
        }
        resize_app();
    });
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = desktop_notifications_panel;
}

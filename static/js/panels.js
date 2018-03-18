var panels = (function () {

var exports = {};

var resize_app = function () {
    var panels_height = $("#panels").height();
    $("body > .app").height("calc(100% - " + panels_height + "px)");
    // the floating recipient bar is usually positioned 10px below the
    // header, so add that to the panels height to get the new `top` value.
    $("#floating_recipient_bar").css("top", panels_height + $(".header").height() + 10 + "px");
};

exports.resize_app = resize_app;

var show_step = function ($process, step) {
    $process.find("[data-step]").hide().filter("[data-step=" + step + "]").show();
};

var get_step = function ($process) {
    return $process.find("[data-step]").filter(":visible").data("step");
};

exports.initialize = function () {
    // if email has not been set up and the user is the admin, display a warning
    // to tell them to set up an email server.
    if (page_params.warn_no_email === true && page_params.is_admin) {
        panels.open($("[data-process='email-server']"));
    } else {
        panels.open($("[data-process='notifications']"));
    }
};

exports.open = function ($process) {
    var ls = localstorage();

    $("[data-process]").hide();

    var should_show_notifications = (
        // notifications *basically* don't work on any mobile platforms, so don't
        // event show the banners. This prevents trying to access things that
        // don't exist like `Notification.permission`.
        !util.is_mobile() &&
        // if permission has not been granted yet.
        !notifications.granted_desktop_notifications_permission() &&
        // if permission is allowed to be requested (e.g. not in "denied" state).
        notifications.permission_state() !== "denied"
    );

    if (localstorage.supported()) {
        // if the user said to never show banner on this computer again, it will
        // be stored as `true` so we want to negate that.
        should_show_notifications = should_show_notifications && !ls.get("dontAskForNotifications");
    }

    if (should_show_notifications) {
        $process.show();
        resize_app();
    }

    // if it is not the notifications prompt, show the error if it has been
    // initialized here.
    if ($process.is(":not([data-process='notifications'])")) {
        $process.show();
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
        if (get_step($process) === 1 && $process.data("process") === "notifications") {
            show_step($process, 2);
        } else {
            $(this).closest(".alert").hide();
        }
        resize_app();
    });
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = panels;
}

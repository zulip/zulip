var settings = (function () {

var exports = {};

$("body").ready(function () {
    var $sidebar = $(".form-sidebar");
    var $targets = $sidebar.find("[data-target]");
    var $title = $sidebar.find(".title h1");
    var is_open = false;

    var close_sidebar = function () {
        $sidebar.removeClass("show");
        is_open = false;
    };

    exports.trigger_sidebar = function (target) {
        $targets.hide();
        var $target = $(".form-sidebar").find("[data-target='" + target + "']");

        $title.text($target.attr("data-title"));
        $target.show();

        $sidebar.addClass("show");
        is_open = true;
    };

    $(".form-sidebar .exit").click(function (e) {
        close_sidebar();
        e.stopPropagation();
    });

    $("body").click(function (e) {
        if (is_open && !$(e.target).within(".form-sidebar")) {
            close_sidebar();
        }
    });

    $("body").on("click", "[data-sidebar-form]", function (e) {
        exports.trigger_sidebar($(this).attr("data-sidebar-form"));
        e.stopPropagation();
    });

    $("body").on("click", "[data-sidebar-form-close]", close_sidebar);
});


function _setup_page() {
    var tab = (function () {
        var tab = false;
        var hash_sequence = window.location.hash.split(/\//);
        if (/#*(settings)/.test(hash_sequence[0])) {
            tab = hash_sequence[1];
            return tab || "your-account";
        }
        return tab;
    }());

    // Most browsers do not allow filenames to start with `.` without the user manually changing it.
    // So we use zuliprc, not .zuliprc.

    var settings_tab = templates.render('settings_tab', {
        full_name: people.my_full_name(),
        page_params: page_params,
        zuliprc: 'zuliprc',
    });

    $(".settings-box").html(settings_tab);

    alert_words_ui.set_up_alert_words();
    attachments_ui.set_up_attachments();
    settings_account.set_up();
    settings_display.set_up();
    settings_notifications.set_up();
    settings_bots.set_up();
    settings_muting.set_up();
    settings_lab.set_up();

    if (tab) {
        exports.launch_page(tab);
    }
}

exports.setup_page = function () {
    i18n.ensure_i18n(_setup_page);
};

exports.launch_page = function (tab) {
    var $active_tab = $("#settings_overlay_container li[data-section='" + tab + "']");

    if (!$active_tab.hasClass("admin")) {
        $(".sidebar .ind-tab[data-tab-key='settings']").click();
    }

    $("#settings_overlay_container").addClass("show");
    $active_tab.click();
};

exports.handle_up_arrow = function (e) {
    var prev = e.target.previousElementSibling;

    if ($(prev).css("display") !== "none") {
        $(prev).focus().click();
    }
};

exports.handle_down_arrow = function (e) {
    var next = e.target.nextElementSibling;

    if ($(next).css("display") !== "none") {
        $(next).focus().click();
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = settings;
}

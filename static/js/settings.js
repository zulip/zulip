var settings = (function () {

var exports = {};
var map;

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

    $("#settings_overlay_container").click(function (e) {
        if (!overlays.is_modal_open()) {
            return;
        }
        if ($(e.target).closest(".modal").length > 0) {
            return;
        }
        e.preventDefault();
        e.stopPropagation();
        overlays.close_active_modal();
    });
});


function _setup_page() {
    ui.set_up_scrollbar($("#settings_page .sidebar.left"));
    ui.set_up_scrollbar($("#settings_content"));

    // only run once -- if the map has not already been initialized.
    if (map === undefined) {
        map = {
            "your-account": i18n.t("Your account"),
            "display-settings": i18n.t("Display settings"),
            notifications: i18n.t("Notifications"),
            "your-bots": i18n.t("Your bots"),
            "alert-words": i18n.t("Alert words"),
            "uploaded-files": i18n.t("Uploaded files"),
            "muted-topics": i18n.t("Muted topics"),
            "zulip-labs": i18n.t("Zulip labs"),
            "organization-profile": i18n.t("Organization profile"),
            "organization-settings": i18n.t("Organization settings"),
            "organization-permissions": i18n.t("Organization permissions"),
            "emoji-settings": i18n.t("Emoji settings"),
            "auth-methods": i18n.t("Authorization methods"),
            "user-list-admin": i18n.t("Active users"),
            "deactivated-users-admin": i18n.t("Deactivated users"),
            "bot-list-admin": i18n.t("Bot list"),
            "streams-list-admin": i18n.t("Streams"),
            "default-streams-list": i18n.t("Default streams"),
            "filter-settings": i18n.t("Filter settings"),
        };
    }

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
        flaskbotrc: 'flaskbotrc',
        timezones: moment.tz.names(),
    });

    $(".settings-box").html(settings_tab);

    // Since we just swapped in a whole new settings widget, we need to
    // tell settings_sections nothing is loaded.
    settings_sections.reset_sections();

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
        components.toggle.lookup("settings-toggle").goto("settings", { dont_switch_tab: true });
    }

    overlays.open_settings();

    $active_tab.click();
};

exports.set_settings_header = function (key) {
    if (map[key]) {
        $(".settings-header h1 .section").text(" / " + map[key]);
    } else {
        blueslip.warn("Error: the key '" + key + "' does not exist in the settings" +
            " header mapping file. Please add it.");
    }
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

var info_overlay = (function () {

var exports = {};

function adjust_mac_shortcuts() {
    var keys_map = [
        ['Backspace', 'Delete'],
        ['Enter', 'Return'],
        ['Home', 'Fn + Left'],
        ['End', 'Fn + Right'],
        ['PgUp', 'Fn + Up'],
        ['PgDn', 'Fn + Down'],
    ];

    $(".hotkeys_table").each(function () {
        var html = $(this).html();
        keys_map.forEach(function (pair) {
            html = html.replace(new RegExp(pair[0]), pair[1]);
        });
        $(this).html(html);
    });
}

function _setup_info_overlay() {
    var info_overlay_toggle = components.toggle({
        name: "info-overlay-toggle",
        selected: 0,
        values: [
            { label: i18n.t("Keyboard shortcuts"), key: "keyboard-shortcuts" },
            { label: i18n.t("Message formatting"), key: "markdown-help" },
            { label: i18n.t("Search operators"), key: "search-operators" },
        ],
        callback: function (name, key) {
            $(".overlay-modal").hide();
            $("#" + key).show();
            $("#" + key).find(".modal-body").focus();
        },
    }).get();

    $(".informational-overlays .overlay-tabs")
        .append($(info_overlay_toggle).addClass("large"));

    if (/Mac/i.test(navigator.userAgent)) {
        adjust_mac_shortcuts();
    }
}

exports.show = function (target) {
    var overlay = $(".informational-overlays");

    if (!overlay.hasClass("show")) {
        overlays.open_overlay({
            name:  'informationalOverlays',
            overlay: overlay,
            on_close: function () {
                hashchange.changehash("");
            },
        });
    }

    if (target) {
        components.toggle.lookup("info-overlay-toggle").goto(target);
    }
};

exports.maybe_show_keyboard_shortcuts = function () {
    if (overlays.is_active()) {
        return;
    }
    if (popovers.any_active()) {
        return;
    }
    exports.show("keyboard-shortcuts");
};

exports.initialize = function () {
    i18n.ensure_i18n(_setup_info_overlay);
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = info_overlay;
}

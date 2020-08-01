exports.night = function () {
    $("body").removeClass("color-scheme-automatic").addClass("night-mode");
};

exports.day = function () {
    $("body").removeClass("color-scheme-automatic").removeClass("night-mode");
};

exports.auto = function () {
    $("body").removeClass("night-mode").addClass("color-scheme-automatic");
};

exports.get_current_theme = function () {
    if ($("body").hasClass("color-scheme-automatic")) {
        return {name: i18n.t("Automatic mode"), short: "Auto", type: "auto"};
    } else if ($("body").hasClass("night-mode")) {
        return {name: i18n.t("Night mode"), short: "Night", type: "night"};
    }
    return {name: i18n.t("Day mode"), short: "Day", type: "day"};
};

window.theme = exports;

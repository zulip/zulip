"use strict";

exports.enable_night_mode = function () {
    $("body").removeClass("color-scheme-automatic").addClass("night-mode");
};

exports.enable_day_mode = function () {
    $("body").removeClass("color-scheme-automatic").removeClass("night-mode");
};

exports.default_preference_checker = function () {
    $("body").removeClass("night-mode").addClass("color-scheme-automatic");
};

window.theme = exports;

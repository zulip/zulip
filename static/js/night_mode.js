"use strict";

exports.enable = function () {
    $("body").removeClass("color-scheme-automatic").addClass("night-mode");
};

exports.disable = function () {
    $("body").removeClass("color-scheme-automatic").removeClass("night-mode");
};

exports.default_preference_checker = function () {
    $("body").removeClass("night-mode").addClass("color-scheme-automatic");
};

window.night_mode = exports;

exports.enable = function () {
    $("body").addClass("night-mode");
};

exports.disable = function () {
    $("body").removeClass("night-mode");
};

window.night_mode = exports;

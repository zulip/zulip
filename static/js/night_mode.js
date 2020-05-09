exports.enable = function () {
    if (!page_params.enable_prefer_color_scheme) {
        $("body").addClass("night-mode");
    }
};

exports.disable = function () {
    $("body").removeClass("night-mode");
};

exports.enable_default_preference = function () {
    $("body").removeClass("night-mode").addClass("dark-preference-checker");
    $("#night_mode").prop('disabled', true);
};

exports.disable_default_preference = function () {
    if (page_params.night_mode) {
        $("body").addClass("night-mode");
    }
    $("body").removeClass("dark-preference-checker");
    $("#night_mode").prop('disabled', false);
};

window.night_mode = exports;

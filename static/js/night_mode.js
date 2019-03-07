var night_mode = (function () {

var exports = {};

exports.initialize = function () {
    if (page_params.night_mode) {
        exports.enable();
    }
};

exports.enable = function () {
    $("body").addClass("night-mode");
};

exports.disable = function () {
    $("body").removeClass("night-mode");
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = night_mode;
}
window.night_mode = night_mode;

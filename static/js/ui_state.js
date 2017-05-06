var ui_state = (function () {

var exports = {};

exports.is_info_overlay = function () {
    return ($(".informational-overlays").hasClass("show"));
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = ui_state;
}

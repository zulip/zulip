var ui_state = (function () {

var exports = {};

exports.home_tab_obscured = function () {
    if ($('.overlay.show').length > 0) {
        return 'modal';
    }

    return false;
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = ui_state;
}

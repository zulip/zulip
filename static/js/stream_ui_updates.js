var stream_ui_updates = (function () {

var exports = {};

exports.update_check_button_for_sub = function (sub) {
    var button = subs.check_button_for_sub(sub);
    if (sub.subscribed) {
        button.addClass("checked");
    } else {
        button.removeClass("checked");
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = stream_ui_updates;
}
window.stream_ui_updates = stream_ui_updates;

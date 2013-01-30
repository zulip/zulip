var notifications_bar = (function () {

var exports = {};

var disabled = false;

function show() {
    $('.notifications').slideDown(50);
}

function hide() {
    $('.notifications').slideUp(50);
}

exports.update = function () {
    if (rows.last_visible().offset() === null)
        return;
    if (rows.last_visible().offset().top + rows.last_visible().height() > viewport.scrollTop() + viewport.height() && !disabled)
        show();
    else
        hide();
};

// We disable the notifications bar if it overlaps with the composebox
exports.maybe_disable = function() {
    if ($("#compose").offset().left + $("#compose").width() > $(".notifications").offset().left) {
        disabled = true;
        exports.update();
    }
};

exports.enable = function() {
    disabled = false;
    exports.update();
};

return exports;
}());

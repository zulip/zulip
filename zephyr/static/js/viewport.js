var viewport = (function () {
var exports = {};

var jwindow;
var height;
var width;

exports.scrollTop = function viewport_scrollTop () {
    return jwindow.scrollTop.apply(jwindow, arguments);
};

exports.height = function viewport_height() {
    if (arguments.length !== 0) {
        height = undefined;
        return jwindow.height.apply(jwindow, arguments);
    }
    if (height === undefined) {
        height = $(window).height();
    }
    return height;
};

exports.width = function viewport_width() {
    if (arguments.length !== 0) {
        width = undefined;
        return jwindow.width.apply(jwindow, arguments);
    }
    if (width === undefined) {
        width = jwindow.width();
    }
    return width;
};

$(function () {
    jwindow = $(window);
    // This handler must be placed before all resize handlers in our application
    jwindow.resize(function () {
        height = undefined;
        width = undefined;
    });
});

return exports;
}());

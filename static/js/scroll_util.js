var scroll_util = (function () {

var exports = {};

exports.scroll_delta = function (opts) {
    var elem_top = opts.elem_top;
    var container_height = opts.container_height;
    var elem_bottom = opts.elem_bottom;

    var delta = 0;

    if (elem_top < 0) {
        delta = Math.max(
            elem_top,
            elem_bottom - container_height
        );
        delta = Math.min(0, delta);
    } else {
        if (elem_bottom > container_height) {
            delta = Math.min(
                elem_top,
                elem_bottom - container_height
            );
            delta = Math.max(0, delta);
        }
    }

    return delta;
};

exports.scroll_element_into_container = function (elem, container) {
    // This does the minimum amount of scrolling that is needed to make
    // the element visible.  It doesn't try to center the element, so
    // this will be non-intrusive to users when they already have
    // the element visible.

    var elem_top = elem.position().top;
    var elem_bottom = elem_top + elem.innerHeight();

    var opts = {
        elem_top: elem_top,
        elem_bottom: elem_bottom,
        container_height: container.height(),
    };

    var delta = exports.scroll_delta(opts);

    if (delta === 0) {
        return;
    }

    container.scrollTop(container.scrollTop() + delta);
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = scroll_util;
}
window.scroll_util = scroll_util;

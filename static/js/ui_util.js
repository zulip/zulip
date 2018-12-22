var ui_util = (function () {

var exports = {};

// Add functions to this that have no non-trivial
// dependencies other than jQuery.

exports.change_tab_to = function (tabname) {
    $('#gear-menu a[href="' + tabname + '"]').tab('show');
};

// http://stackoverflow.com/questions/4233265/contenteditable-set-caret-at-the-end-of-the-text-cross-browser
exports.place_caret_at_end = function (el) {
    el.focus();

    if (typeof window.getSelection !== "undefined"
            && typeof document.createRange !== "undefined") {
        var range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        var sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    } else if (typeof document.body.createTextRange !== "undefined") {
        var textRange = document.body.createTextRange();
        textRange.moveToElementText(el);
        textRange.collapse(false);
        textRange.select();
    }
};

exports.blur_active_element = function () {
    // this blurs anything that may perhaps be actively focused on.
    document.activeElement.blur();
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = ui_util;
}
window.ui_util = ui_util;

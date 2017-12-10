var compose_ui = (function () {

var exports = {};

exports.autosize_textarea = function () {
    $("#compose-textarea").trigger("autosize.resize");
};

exports.smart_insert = function (textarea, syntax) {
    function is_space(c) {
        return (c === ' ') || (c === '\t') || (c === '\n');
    }

    var pos = textarea.caret();
    var before_str = textarea.val().slice(0, pos);
    var after_str = textarea.val().slice(pos);

    if (pos > 0) {
        if (!is_space(before_str.slice(-1))) {
            syntax = ' ' + syntax;
        }
    }

    if (after_str.length > 0) {
        if (!is_space(after_str[0])) {
            syntax += ' ';
        }
    }

    textarea.focus();
    // execCommand is used to enable rich-text editing feature of browser like
    // To insert text into compose box through events(inserting emoji, video link etc.)
    // But this function is not cross-browser, so we will have to take if this returns
    // false(which means function is not supported by particular browser)
    if (!document.execCommand("insertText", false, syntax)) {
        textarea.caret(syntax);
    }

    // This should just call exports.autosize_textarea, but it's a bit
    // annoying for the unit tests, so we don't do that.
    textarea.trigger("autosize.resize");
};

exports.insert_syntax_and_focus = function (syntax) {
    // Generic helper for inserting syntax into the main compose box
    // where the cursor was and focusing the area.  Mostly a thin
    // wrapper around smart_insert.
    var textarea = $('#compose-textarea');
    exports.smart_insert(textarea, syntax);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}

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

    if (!(after_str.length > 0 && is_space(after_str[0]))) {
            syntax += ' ';
        }

    textarea.focus();

    // We prefer to use insertText, which supports things like undo better
    // for rich-text editing features like inserting links.  But we fall
    // back to textarea.caret if the browser doesn't support insertText.
    if (!document.execCommand("insertText", false, syntax)) {
        textarea.caret(syntax);
    }

    // This should just call exports.autosize_textarea, but it's a bit
    // annoying for the unit tests, so we don't do that.
    textarea.trigger("autosize.resize");
};

exports.insert_syntax_and_focus = function (syntax, textarea) {
    // Generic helper for inserting syntax into the main compose box
    // where the cursor was and focusing the area.  Mostly a thin
    // wrapper around smart_insert.
    if (textarea === undefined) {
        textarea = $('#compose-textarea');
    }
    exports.smart_insert(textarea, syntax);
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}

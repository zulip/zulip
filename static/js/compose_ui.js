var compose_ui = (function () {

var exports = {};

exports.autosize_textarea = function () {
    $("#compose-textarea").trigger("autosize.resize");
};

exports.smart_insert = function (textarea, syntax) {
    function is_space(c) {
        return c === ' ' || c === '\t' || c === '\n';
    }

    var pos = textarea.caret();
    var before_str = textarea.val().slice(0, pos);
    var after_str = textarea.val().slice(pos);

    if (pos > 0) {
        // If there isn't space either at the end of the content
        // before the insert or (unlikely) at the start of the syntax,
        // add one.
        if (!is_space(before_str.slice(-1)) && !is_space(syntax[0])) {
            syntax = ' ' + syntax;
        }
    }

    // If there isn't whitespace either at the end of the syntax or the
    // start of the content after the syntax, add one.
    if (!(after_str.length > 0 && is_space(after_str[0]) ||
          syntax.length > 0 && is_space(syntax.slice(-1)))) {
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

exports.replace_syntax = function (old_syntax, new_syntax, textarea) {
    // Replaces `old_syntax` with `new_syntax` text in the compose box. Due to
    // the way that JavaScript handles string replacements, if `old_syntax` is
    // a string it will only replace the first instance. If `old_syntax` is
    // a RegExp with a global flag, it will replace all instances.

    if (textarea === undefined) {
        textarea = $('#compose-textarea');
    }

    textarea.val(textarea.val().replace(old_syntax, new_syntax));
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}
window.compose_ui = compose_ui;

var compose_ui = (function () {

var exports = {};

exports.autosize_textarea = function () {
    $("#new_message_content").trigger("autosize.resize");
};

exports.insert_syntax_and_focus = function (syntax) {
    // Generic helper for inserting syntax into the main compose box
    // where the cursor was and focusing the area.  Mostly a thin
    // wrapper around $.caret.
    var textarea = $('#new_message_content');
    textarea.caret(syntax);
    textarea.focus();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}

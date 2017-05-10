var compose_ui = (function () {

var exports = {};

exports.autosize_textarea = function () {
    $("#new_message_content").trigger("autosize.resize");
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}

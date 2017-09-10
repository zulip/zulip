var compose_ui = (function () {

var exports = {};

exports.autosize_textarea = function () {
    autosize.update($("#new_message_content"));
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}

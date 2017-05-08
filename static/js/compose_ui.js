var compose_ui = (function () {

var exports = {};

exports.autosize_textarea = function () {
    $("#new_message_content").trigger("autosize.resize");
};

exports.empty_topic_placeholder = function () {
    return i18n.t("(no topic)");
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = compose_ui;
}

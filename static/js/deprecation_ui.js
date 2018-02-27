var deprecation_ui = (function () {

var exports = {};

function get_deprecation_message_display_status() {
    var deprecation_message_display_status = localStorage.getItem('deprecation_message_display_status');
    if (deprecation_message_display_status === null) {
        deprecation_message_display_status = JSON.parse('{}');
    } else {
        deprecation_message_display_status = JSON.parse(deprecation_message_display_status);
    }
    return deprecation_message_display_status;
}

function update_deprecation_message_display_status(deprecation_message_display_status) {
    localStorage.setItem('deprecation_message_display_status', JSON.stringify(deprecation_message_display_status));
}

exports.display_deprecation_modal = function (opts) {
    var trigger_key = opts.trigger_key;
    var deprecation_message_display_status = get_deprecation_message_display_status();

    if (!deprecation_message_display_status[trigger_key]) {
        var deprecation_modal = $('#deprecation-modal');
        var deprecation_modal_message = $('#deprecation-modal-message');
        var deprecation_modal_message_text = opts.message;

        deprecation_modal.modal('show');
        deprecation_modal_message.text(i18n.t(deprecation_modal_message_text));

        deprecation_message_display_status[trigger_key] = true;
        update_deprecation_message_display_status(deprecation_message_display_status);
    }

};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = deprecation_ui;
}

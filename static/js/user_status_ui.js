var user_status_ui = (function () {

var exports = {};

exports.input_field = function () {
    return $('.user_status_overlay input.user_status');
};

exports.submit_button = function () {
    return $('.user_status_overlay .set_user_status');
};

exports.open_overlay = function () {
    var overlay = $(".user_status_overlay");
    overlays.open_overlay({
        name: 'user_status_overlay',
        overlay: overlay,
        on_close: function () {},
    });

    var user_id = people.my_current_user_id();
    var old_status_text = user_status.get_status_text(user_id);
    var field = exports.input_field();
    field.val(old_status_text);
    field.select();
    field.focus();

    var button = exports.submit_button();
    button.attr('disabled', true);
};

exports.close_overlay = function () {
    overlays.close_overlay('user_status_overlay');
};

exports.submit_new_status = function () {
    var user_id = people.my_current_user_id();
    var old_status_text = user_status.get_status_text(user_id) || '';
    old_status_text = old_status_text.trim();
    var new_status_text = exports.input_field().val().trim();

    if (old_status_text === new_status_text) {
        exports.close_overlay();
        return;
    }

    user_status.server_update({
        status_text: new_status_text,
        success: function () {
            exports.close_overlay();
        },
    });
};

exports.update_button = function () {
    var user_id = people.my_current_user_id();
    var old_status_text = user_status.get_status_text(user_id) || '';
    old_status_text = old_status_text.trim();
    var new_status_text = exports.input_field().val().trim();
    var button = exports.submit_button();

    if (old_status_text === new_status_text) {
        button.attr('disabled', true);
    } else {
        button.attr('disabled', false);
    }
};

exports.initialize = function () {
    $('body').on('click', '.user_status_overlay .set_user_status', function () {
        exports.submit_new_status();
    });

    $('body').on('keyup', '.user_status_overlay input.user_status', function () {
        exports.update_button();
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = user_status_ui;
}
window.user_status_ui = user_status_ui;

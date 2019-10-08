var confirm_dialog = (function () {

var exports = {};

/*
    Look for confirm_dialog in settings_user_groups
    to see an example of how to use this widget.  It's
    pretty simple to use!

    Some things to note:

        1) We create DOM on the fly, and we remove
           the DOM once it's closed.

        2) We attach the DOM for the modal to conf.parent,
           and this temporary DOM location will influence
           how styles work.

        3) The cancel button is driven by bootstrap.js.

        4) For settings, we have a click handler in settings.js
           that will close the dialog via overlays.close_active_modal.

        5) We assume that since this is a modal, you will
           only ever have one confirm dialog active at any
           time.

*/

exports.launch = function (conf) {
    var html = templates.render("confirm_dialog");
    var confirm_dialog = $(html);

    var conf_fields = [
        // The next three fields should be safe HTML. If callers
        // interpolate user data into strings, they should use
        // templates.
        'html_heading',
        'html_body',
        'html_yes_button',
        'on_click',
        'parent',
    ];

    _.each(conf_fields, function (f) {
        if (!conf[f]) {
            blueslip.error('programmer omitted ' + f);
        }
    });

    conf.parent.append(confirm_dialog);

    // Close any existing modals--on settings screens you can
    // have multiple buttons that need confirmation.
    if (overlays.is_modal_open()) {
        overlays.close_modal('confirm_dialog_modal');
    }

    confirm_dialog.find('.confirm_dialog_heading').html(conf.html_heading);
    confirm_dialog.find('.confirm_dialog_body').html(conf.html_body);

    var yes_button = confirm_dialog.find('.confirm_dialog_yes_button');

    yes_button.html(conf.html_yes_button);

    // Set up handlers.
    yes_button.on('click', function () {
        overlays.close_modal('confirm_dialog_modal');
        conf.on_click();
    });

    confirm_dialog.on('hide', function () {
        confirm_dialog.remove();
    });

    // Open the modal
    overlays.open_modal('confirm_dialog_modal');
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = confirm_dialog;
}
window.confirm_dialog = confirm_dialog;

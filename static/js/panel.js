var panel = (function () {

var exports = {};

function show_element_with_id(id) {
    $('#' + id).css({ 'margin-bottom' : '0px'});
    $('#' + id).show();
}


function display_panel() {
    if (!page_params.needs_tutorial &&
        !notifications.granted_desktop_notifications_permission()) {
        show_element_with_id('desktop-notifications-panel');
    }
}

exports.initialize = function () {
    $('#request-desktop-notifications').on('click', function () {
        $('#desktop-notifications-panel').hide();
        notifications.request_desktop_notifications_permission();
    });
    display_panel();
};

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = panel;
}

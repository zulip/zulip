var kiosk = (function () {

var exports = {};

exports.enable = function () {
    exports.kiosk_mode_enabled = true;

    // Make layout look correct
    $("body").css('padding', 5);
    $(".container-fluid").css('padding', 0);
    $(".message_area_padder").css('padding', 0);
    $(".tab-content").removeClass("span8");

    // Firefox seems to require this, otherwise it draws a scrollbar.
    $("#home").css('overflow', 'hidden');

    $(".hidden-phone").hide();
    $(".navbar").hide();
    $("#navbar-spacer").hide();

    $("#compose").hide();
    $("#bottom_whitespace").hide();
    $("#tab_bar").parent().hide();

    $("#floating_recipient_bar").css('top', 0);
    $(".message_area_padder").css('margin', 0);
    ui.resize_page_components();

    // Disable message sending, narrowing, actions popover
    compose.start = function () { return; };
    narrow.activate = function () { return; };
    popovers.show_actions_popover = function () { return; };
    // Disable hotkeys? Seems like this is not necessary after the
    // above, and keeping them around lets us scroll nicely.

    // TODO: Is it going to prompt for notifications?
    // My guess is that it probably won't if we disable notifications
    // for the iframe user, but who knows.
};

exports.update_new_messages = function () {
    if (exports.kiosk_mode_enabled !== true) {
        return;
    }
    // Format messages properly & scroll to last message
    $(".message_controls").hide();
    $(".message_time").css('right', -65);
    navigate.to_end();
};

exports.kiosk_mode_enabled = false;
$(function () {
    if (feature_flags.kiosk_mode) {
        exports.enable();
    }
});

return exports;

}());

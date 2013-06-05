var notifications_bar = (function () {

var exports = {};

var disabled = false; // true when the bar should be hidden (eg, it's blocking the composebox)
var displayed = false; // true when the bar is supposedly displayed (ignoring disabled-ness)
var bar_selector = "#notifications-bar"; // the selector jQuery can use to pick the notifications bar
var area_selector = "#notifications-area"; // the selector jQuery can use to pick the container

function show() {
    if (disabled)
        return; // we should never show the bar when disabled

    if (!displayed) {
        // If the bar wasn't already displayed, simply show it
        $(bar_selector).text("More messages below").slideDown(50);
        displayed = true; // we need to set this flag
    }
}

// Hide the notifications bar
function hide() {
    if (!displayed)
        return; // don't unnecessarily add to the element's fx queue
    displayed = false;
    $(bar_selector).slideUp(50);
}

// If there's a custom message, or if the last message is off the bottom of the
// screen, then show the notifications bar.
exports.update = function (num_unread) {
    if (rows.last_visible().offset() !== null // otherwise the next line will error
        && rows.last_visible().offset().top + rows.last_visible().height() > viewport.scrollTop() + viewport.height() - $("#compose").height()
        && num_unread > 0)
        show();
    else
        hide();
};

// We disable the notifications bar if it overlaps with the composebox
exports.maybe_disable = function() {
    if ($("#compose").offset().left + $("#compose").width() > $(area_selector).offset().left) {
        disabled = true;
        hide();
    }
};

// Un-disable the notifications bar, then call the update function to see if it should be displayed
exports.enable = function() {
    disabled = false;
    exports.update();
};

return exports;
}());

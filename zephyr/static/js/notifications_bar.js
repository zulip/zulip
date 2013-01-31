var notifications_bar = (function () {

var exports = {};

var disabled = false; // true when the bar should be hidden (eg, it's blocking the composebox)
var displayed = false; // true when the bar is supposedly displayed (ignoring disabled-ness)
var on_custom = false; // true when the bar is showing a custom message
var custom_message = ""; // the current custom message being displayed, if any
var current_message = ""; // the current notification being displayed in the bar, if any
var timeoutID = null; // keeping track of the clear_custom_message timer, so we can cancel it
var bar_selector = "#notifications-bar"; // the selector jQuery can use to pick the notifications bar
var area_selector = "#notifications-area"; // the selector jQuery can use to pick the container

// Try to show msg (but this might fail if the bar is disabled)
function show(msg) {
    if (disabled)
        return; // we should never show the bar when disabled

    if (displayed && msg !== current_message) {
        // If the bar is already displayed and we're changing the text, show an animation
        var changeText = function () {
            // Custom effect to put change of text in the queue (after slideUp)
            $(this).text(msg);
            $(this).dequeue();
        };
        $(bar_selector).slideUp(50).queue(changeText).delay(100).slideDown(50);
    } else if (!displayed) {
        // If the bar wasn't already displayed, simply show it
        $(bar_selector).text(msg).slideDown(50);
        displayed = true; // we need to set this flag
    }
    // In the last case (the bar is already displayed and has the right text), do nothing

    // We can't use $(bar_selector).text() to get the current notification
    // because, in one of the cases above, the text isn't actually changed
    // immediately. Instead, let's store the current notification in a global
    // variable.
    current_message = msg;
}

// Hide the notifications bar
function hide() {
    if (!displayed)
        return; // don't unnecessarily add to the element's fx queue
    displayed = false;
    current_message = "";
    $(bar_selector).slideUp(50);
}

// If there's a custom message, or if the last message is off the bottom of the
// screen, then show the notifications bar.
exports.update = function () {
    if (on_custom)
        show(custom_message);
    else if (rows.last_visible().offset() !== null // otherwise the next line will error
        && rows.last_visible().offset().top + rows.last_visible().height() > viewport.scrollTop() + viewport.height())
        show("More messages below");
    else
        hide();
};

// Clear the custom message and go back to the default (called by a timer)
function clear_custom_message() {
    on_custom = false;
    custom_message = "";
    timeoutID = null;
    exports.update();
}

// Show the message msg for duration milliseconds. If the notifications bar is
// hidden by the composebox, the timer still ticks. Also, if this method is
// called again, the new message will overwrite the old one.
exports.show_custom_message = function (msg, duration) {
    if (timeoutID !== null)
        window.clearTimeout(timeoutID); // clear any existing timers
    on_custom = true;
    custom_message = msg;
    show(msg);
    timeoutID = window.setTimeout(clear_custom_message, duration);
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

var gear_menu = (function () {

var exports = {};

// We want to remember how far we were scrolled on each 'tab'.
// To do so, we need to save away the old position of the
// scrollbar when we switch to a new tab (and restore it
// when we switch back.)
var scroll_positions = {};

exports.initialize = function () {
    i18n.ensure_i18n(admin.show_or_hide_menu_item);

    $('#gear-menu a[data-toggle="tab"]').on('show', function (e) {
        // Save the position of our old tab away, before we switch
        var old_tab = $(e.relatedTarget).attr('href');
        scroll_positions[old_tab] = message_viewport.scrollTop();
    });
    $('#gear-menu a[data-toggle="tab"]').on('shown', function (e) {
        var target_tab = $(e.target).attr('href');
        resize.resize_bottom_whitespace();
        // Hide all our error messages when switching tabs
        $('.alert').removeClass("show");

        // Set the URL bar title to show the sub-page you're currently on.
        var browser_url = target_tab;
        if (browser_url === "#home") {
            browser_url = "";
        }
        hashchange.changehash(browser_url);

        // After we show the new tab, restore its old scroll position
        // (we apparently have to do this after setting the hash,
        // because otherwise that action may scroll us somewhere.)
        if (target_tab === '#home') {
            if (scroll_positions.hasOwnProperty(target_tab)) {
                message_viewport.scrollTop(scroll_positions[target_tab]);
            } else {
                navigate.scroll_to_selected();
            }
        }
    });

    // The admin and settings pages are generated client-side through
    // templates.
};

exports.open = function () {
    $("#settings-dropdown").click();
    // there are invisible li tabs, which should not be clicked.
    $("#gear-menu").find("li:not(.invisible) a").eq(0).focus();
};

exports.is_open = function () {
    return $(".dropdown").hasClass("open");
};

exports.close = function () {
    if (exports.is_open()) {
        $(".dropdown").removeClass("open");
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = gear_menu;
}

var modals = (function () {

var exports = {};

exports.close = {};

exports.open_overlay = function (opts) {
    if (!opts.name || !opts.overlay || !opts.on_close) {
        blueslip.error('Programming error in open_modal');
        return;
    }

    // Our overlays are kind of crufty...we have an HTML id
    // attribute for them and then a data-overlay attribute for
    // them.  Make sure they match.
    if (opts.overlay.attr('data-overlay') !== opts.name) {
        blueslip.error('Bad overlay setup for ' + opts.name);
        return;
    }

    opts.overlay.addClass('show');

    exports.close[opts.name] = function () {
        opts.on_close();
        exports.close[opts.name] = undefined;
    };
};

exports.set_close_handler = function (name, handler) {
    exports.close[name] = handler;
};

exports.close_modal = function (name) {
    $("[data-overlay='" + name + "']").removeClass("show");

    if (exports.close[name]) {
        exports.close[name]();
    } else {
        blueslip.error("Modal close handler for " + name + " not properly setup." );
    }
};

exports.open_settings = function () {
    modals.open_overlay({
        name: 'settings',
        overlay: $("#settings_overlay_container"),
        on_close: function () {
            hashchange.exit_modal();
        },
    });
};

$(function () {
    $("body").on("click", ".overlay, .overlay .exit", function (e) {
        var $target = $(e.target);

        // if the target is not the .overlay element, search up the node tree
        // until it is found.
        if ($target.is(".exit, .exit-sign, .overlay-content")) {
            $target = $target.closest("[data-overlay]");
        } else if (!$target.is(".overlay")) {
            // not a valid click target then.
            return;
        }

        var target_name = $target.attr("data-overlay");

        $target.removeClass("show");

        // if an appropriate clearing/closing function for a modal exists,
        // execute it.
        if (exports.close[target_name]) {
            exports.close[target_name]();
        } else {
            blueslip.error("Tried to close unknown modal " + target_name);
        }

        e.preventDefault();
        e.stopPropagation();
    });
});

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = modals;
}

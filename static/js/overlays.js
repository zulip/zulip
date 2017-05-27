var overlays = (function () {

var exports = {};

var active_overlay;
var close_handler;
var open_overlay_name;

function reset_state() {
    active_overlay = undefined;
    close_handler = undefined;
    open_overlay_name = undefined;
}

exports.is_active = function () {
    return !!open_overlay_name;
};

exports.info_overlay_open = function () {
    return open_overlay_name === 'informationalOverlays';
};

exports.settings_open = function () {
    return open_overlay_name === 'settings';
};

exports.streams_open = function () {
    return open_overlay_name === 'subscriptions';
};

exports.lightbox_open = function () {
    return open_overlay_name === 'lightbox';
};

exports.open_overlay = function (opts) {
    if (!opts.name || !opts.overlay || !opts.on_close) {
        blueslip.error('Programming error in open_overlay');
        return;
    }

    if (active_overlay || open_overlay_name || close_handler) {
        blueslip.error('Programming error--trying to open ' + opts.name +
            ' before closing ' + open_overlay_name);
        return;
    }

    // Our overlays are kind of crufty...we have an HTML id
    // attribute for them and then a data-overlay attribute for
    // them.  Make sure they match.
    if (opts.overlay.attr('data-overlay') !== opts.name) {
        blueslip.error('Bad overlay setup for ' + opts.name);
        return;
    }

    open_overlay_name = opts.name;
    active_overlay = opts.overlay;
    opts.overlay.addClass('show');

    close_handler = function () {
        opts.on_close();
        reset_state();
    };
};

exports.close_overlay = function (name) {
    if (name !== open_overlay_name) {
        blueslip.error("Trying to close " + name + " when " + open_overlay_name + " is open." );
        return;
    }

    active_overlay.removeClass("show");

    if (!close_handler) {
        blueslip.error("Overlay close handler for " + name + " not properly setup." );
        return;
    }

    close_handler();
};

exports.close_active = function () {
    if (!open_overlay_name) {
        blueslip.warn('close_active() called without checking is_active()');
        return;
    }

    exports.close_overlay(open_overlay_name);
};

exports.close_for_hash_change = function () {
    $(".overlay.show").removeClass("show");
    reset_state();
};

exports.open_settings = function () {
    overlays.open_overlay({
        name: 'settings',
        overlay: $("#settings_overlay_container"),
        on_close: function () {
            hashchange.exit_overlay();
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

        exports.close_overlay(target_name);

        e.preventDefault();
        e.stopPropagation();
    });
});

return exports;

}());

if (typeof module !== 'undefined') {
    module.exports = overlays;
}

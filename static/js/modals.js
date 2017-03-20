var modals = (function () {
    "use strict";

    var exports = {
        close: {
            subscriptions: function () {
                subs.close();
            },

            drafts: function () {
                hashchange.exit_modal();
            },

            informationalOverlays: function () {
                $(".informational-overlays").removeClass("show");
            },

            settings: function () {
                hashchange.exit_modal();
            },

            lightbox: function () {
                $(".player-container iframe").remove();
                lightbox.is_open = false;
                document.activeElement.blur();
            },

            invite: function () {
                hashchange.exit_modal();
            },
        },

        close_modal: function (name) {
            $("[data-overlay='" + name + "']").removeClass("show");

            if (exports.close[name]) {
                exports.close[name]();
            }
        },
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

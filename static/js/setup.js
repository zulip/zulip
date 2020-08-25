"use strict";

const util = require("./util");

// Miscellaneous early setup.
exports.password_change_in_progress = false;
$(() => {
    if (util.is_mobile()) {
        // Disable the tutorial; it's ugly on mobile.
        page_params.needs_tutorial = false;
    }

    page_params.page_load_time = new Date().getTime();

    // Display loading indicator.  This disappears after the first
    // get_events completes.
    if (!page_params.needs_tutorial) {
        loading.make_indicator($("#page_loading_indicator"), {
            text: "Loading...",
            abs_positioned: true,
        });
    }

    // This is an issue fix where in jQuery v3 the result of outerHeight on a node
    // that doesn’t exist is now “undefined” rather than “null”, which means it
    // will no longer cast to a Number but rather NaN. For this, we create the
    // `safeOuterHeight` and `safeOuterWidth` functions to safely return a result
    // (or 0).
    $.fn.safeOuterHeight = function (...args) {
        return this.outerHeight(...args) || 0;
    };

    $.fn.safeOuterWidth = function (...args) {
        return this.outerWidth(...args) || 0;
    };

    // For some reason, jQuery wants this to be attached to an element.
    $(document).ajaxError((event, xhr) => {
        // Don't redirect to the login page when a password change
        // is in progress. Since 401 in that process means this is
        // a race condition caused by a request that was made just
        // before the session hash was updated in the backend.
        if (xhr.status === 401 && !exports.password_change_in_progress) {
            // We got logged out somehow, perhaps from another window or a session timeout.
            // We could display an error message, but jumping right to the login page seems
            // smoother and conveys the same information.
            window.location.replace(page_params.login_page);
        }
    });

    if (typeof $ !== "undefined") {
        $.fn.expectOne = function () {
            if (blueslip && this.length !== 1) {
                blueslip.error("Expected one element in jQuery set, " + this.length + " found");
            }
            return this;
        };

        $.fn.within = function (sel) {
            return $(this).is(sel) || $(this).closest(sel).length;
        };
    }
});

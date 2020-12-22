"use strict";

const util = require("./util");

// Miscellaneous early setup.
exports.password_change_in_progress = false;

exports.set_password_change_in_progress = function (value) {
    exports.password_change_in_progress = value;
};

$(() => {
    if (util.is_mobile()) {
        // Disable the tutorial; it's ugly on mobile.
        page_params.needs_tutorial = false;
    }

    page_params.page_load_time = Date.now();

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
        if (exports.password_change_in_progress) {
            // The backend for handling password change API requests
            // will replace the user's session; this results in a
            // brief race where any API request will fail with a 401
            // error after the old session is deactivated but before
            // the new one has been propagated to the browser.  So we
            // skip our normal HTTP 401 error handling if we're in the
            // process of executing a password change.
            return;
        }

        if (xhr.status === 401) {
            // We got logged out somehow, perhaps from another window
            // changing the user's password, or a session timeout.  We
            // could display an error message, but jumping right to
            // the login page conveys the same information with a
            // smoother re-login experience.
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

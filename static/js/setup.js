import $ from "jquery";

import * as blueslip from "./blueslip";
import * as loading from "./loading";
import {page_params} from "./page_params";
import * as util from "./util";

// Miscellaneous early setup.
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

    $.fn.expectOne = function () {
        if (blueslip && this.length !== 1) {
            blueslip.error("Expected one element in jQuery set, " + this.length + " found");
        }
        return this;
    };
});

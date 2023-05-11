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
            abs_positioned: true,
        });
    }

    $.fn.expectOne = function () {
        if (blueslip && this.length !== 1) {
            blueslip.error("Expected one element in jQuery set, found more", {length: this.length});
        }
        return this;
    };
});

import $ from "jquery";

import * as blueslip from "./blueslip.ts";
import * as loading from "./loading.ts";
import * as util from "./util.ts";

export let page_load_time: number | undefined;

// Miscellaneous early setup.
$(() => {
    page_load_time = Date.now();

    // Display loading indicator.  This disappears after the first
    // get_events completes.
    loading.make_indicator($("#page_loading_indicator"), {
        abs_positioned: true,
    });

    $.fn.get_offset_to_window = function () {
        return util.the(this).getBoundingClientRect();
    };

    $.fn.expectOne = function () {
        if (blueslip && this.length !== 1) {
            blueslip.error("Expected one element in jQuery set", {length: this.length});
        }
        return this;
    };
});

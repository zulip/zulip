import $ from "jquery";

import {page_params} from "../page_params";

import render_tabs from "./team";

export function path_parts() {
    return window.location.pathname.split("/").filter((chunk) => chunk !== "");
}

$(() => {
    if (window.location.pathname === "/team/") {
        const contributors = page_params.contributors;
        delete page_params.contributors;
        render_tabs(contributors);
    }
});

// Scroll to anchor link when clicked. Note that help.js has a similar
// function; this file and help.js are never included on the same
// page.
$(document).on("click", ".markdown h1, .markdown h2, .markdown h3", function () {
    window.location.hash = $(this).attr("id");
});

import $ from "jquery";

export function path_parts() {
    return window.location.pathname.split("/").filter((chunk) => chunk !== "");
}

// Scroll to anchor link when clicked. Note that help.js has a similar
// function; this file and help.js are never included on the same
// page.
$(document).on("click", ".markdown h1, .markdown h2, .markdown h3", function () {
    window.location.hash = $(this).attr("id");
});

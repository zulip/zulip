window.page_params = $("#page-params").remove().data("params");
if (!window.page_params) {
    throw new Error("Missing page-params");
}

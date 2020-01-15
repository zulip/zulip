const t1 = performance.now();
window.page_params = $("#page-params").remove().data("params");
const t2 = performance.now();
window.page_params_parse_time = t2 - t1;
if (!window.page_params) {
    throw new Error("Missing page-params");
}

var feature_flags = (function () {

var exports = {};

exports.always_open_compose =  true;
exports.mark_read_at_bottom = page_params.staging;
exports.summarize_read_while_narrowed = page_params.staging;

return exports;

}());

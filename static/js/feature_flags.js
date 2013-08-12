var feature_flags = (function () {

var exports = {};

exports.always_open_compose =  true;
exports.mark_read_at_bottom = page_params.staging;
exports.summarize_read_while_narrowed = page_params.staging;
exports.twenty_four_hour_time = _.contains([],
                                  page_params.email);
return exports;

}());

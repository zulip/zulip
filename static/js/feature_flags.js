var feature_flags = (function () {

var exports = {};

exports.always_open_compose =  true;
exports.mark_read_at_bottom = page_params.staging;
exports.summarize_read_while_narrowed = page_params.staging;
exports.twenty_four_hour_time = _.contains([],
                                  page_params.email);
exports.dropbox_integration = page_params.staging || _.contains(['dropbox.com'], page_params.domain);
return exports;

}());

var feature_flags = (function () {

var exports = {};

exports.always_open_compose =  _.contains(['mit.edu',
                                           'customer4.invalid',
                                           'users.customer4.invalid',
                                           'zulip.com'],
                                          page_params.domain);

exports.mark_read_at_bottom = page_params.staging;

return exports;

}());

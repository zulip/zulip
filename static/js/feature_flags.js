var feature_flags = (function () {

var exports = {};

exports.mark_read_at_bottom = page_params.staging;
exports.summarize_read_while_narrowed = page_params.staging;
exports.twenty_four_hour_time = _.contains([],
                                  page_params.email);
exports.dropbox_integration = page_params.staging || _.contains(['dropbox.com'], page_params.domain);
exports.email_forwarding = page_params.staging;
exports.edit_appears_on_hover = page_params.staging || _.contains(['customer7.invalid'], page_params.domain);


exports.mandatory_topics = _.contains([
    'customer7.invalid'
    ],
    page_params.domain
);

exports.collapsible = false;

return exports;

}());

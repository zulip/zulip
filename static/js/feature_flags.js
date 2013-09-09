var feature_flags = (function () {

var exports = {};

exports.mark_read_at_bottom = page_params.staging ||
                              _.contains(['mit.edu'], page_params.domain);
exports.summarize_read_while_narrowed = page_params.staging;
exports.twenty_four_hour_time = _.contains([],
                                  page_params.email);
exports.dropbox_integration = page_params.staging || _.contains(['dropbox.com'], page_params.domain);
exports.email_forwarding = true;

exports.mandatory_topics = _.contains([
    'customer7.invalid'
    ],
    page_params.domain
);

exports.collapsible = page_params.staging;

exports.propagate_topic_edits = page_params.staging ||
  _.contains(['customer7.invalid'], page_params.domain);

exports.fade_users_when_composing = page_params.staging;

exports.alert_words = page_params.staging ||
  _.contains(['reddit.com'], page_params.domain);

return exports;

}());

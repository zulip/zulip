var feature_flags = (function () {

var exports = {};

exports.mark_read_at_bottom = true;
exports.summarize_read_while_narrowed = true;

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

exports.muting = page_params.staging;

exports.left_side_userlist = page_params.staging ||
  _.contains(['customer7.invalid'], page_params.domain);

return exports;

}());

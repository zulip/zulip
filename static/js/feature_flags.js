var feature_flags = (function () {

var exports = {};

exports.mark_read_at_bottom = true;
exports.summarize_read_while_narrowed = true;

var internal_24_hour_people= _.contains([],
    page_params.email);

var iceland = page_params.domain === 'customer8.invalid';

exports.twenty_four_hour_time = internal_24_hour_people || iceland;

exports.dropbox_integration = page_params.staging || _.contains(['dropbox.com'], page_params.domain);

exports.mandatory_topics = _.contains([
    'customer7.invalid'
    ],
    page_params.domain
);

exports.collapsible = page_params.staging;

exports.propagate_topic_edits = page_params.staging ||
  _.contains(['customer7.invalid'], page_params.domain);

var customer4_realms = [
  'customer4.invalid',
  'users.customer4.invalid'
];
var is_customer4 = _.contains(customer4_realms, page_params.domain);

exports.fade_users_when_composing = page_params.staging || is_customer4;

exports.alert_words =
  _.contains(['reddit.com', 'mit.edu', 'zulip.com'], page_params.domain);


var zulip_mit_emails = [];

var is_zulip_mit_user = _.contains(zulip_mit_emails, page_params.email);

exports.muting = page_params.staging || is_zulip_mit_user;

exports.left_side_userlist = page_params.staging ||
  _.contains(['customer7.invalid'], page_params.domain);

return exports;

}());

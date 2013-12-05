var feature_flags = (function () {

var exports = {};

// Helpers
var internal_24_hour_people= _.contains([],
    page_params.email);

var zulip_mit_emails = [];
var is_zulip_mit_user = _.contains(zulip_mit_emails, page_params.email);

var iceland = page_params.domain === 'customer8.invalid';

var customer4_realms = [
  'customer4.invalid',
  'users.customer4.invalid'
];
var is_customer4 = _.contains(customer4_realms, page_params.domain);

// Enterprise-related flags
exports.do_not_share_the_love = page_params.enterprise;

// Manually-flipped debugging flags
exports.log_send_times = false;
exports.collect_send_times = false;

// Permanent realm-specific stuff:
exports.disable_message_editing = _.contains(['mit.edu'], page_params.domain);

exports.twenty_four_hour_time = internal_24_hour_people || iceland;

exports.dropbox_integration = page_params.staging || _.contains(['dropbox.com'], page_params.domain);

exports.mandatory_topics = _.contains([
    'customer7.invalid'
    ],
    page_params.domain
);

exports.left_side_userlist = _.contains(['customer7.invalid'], page_params.domain);


// Still very beta:
exports.fade_users_when_composing = page_params.staging || is_customer4;
exports.use_socket = false;

exports.clicking_notification_causes_narrow = page_params.staging || is_customer4 ||
    _.contains(['customer25.invalid'], page_params.domain);

exports.experimental_background = page_params.staging || _.contains(['mit.edu'], page_params.domain);

exports.show_digest_email_setting = page_params.staging;

var zoom_realms = [
    'customer4.invalid',
    'users.customer4.invalid',
    'customer10.invalid',
    'upworthy.com',
    'mit.edu',
    'cmtelematics.com'
];
exports.topic_zooming = page_params.staging || _.contains(zoom_realms, page_params.domain);

// Still burning in...
exports.mark_read_at_bottom = true;
exports.propagate_topic_edits = true;
exports.summarize_read_while_narrowed = false;

// Ready for deprecation.
exports.collapsible = false;

return exports;

}());

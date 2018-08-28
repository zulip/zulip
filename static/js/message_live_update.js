var message_live_update = (function () {

var exports = {};

exports.update_stream_name = function (stream_id, new_name) {
    _.each([home_msg_list, message_list.narrowed, message_list.all], function (list) {
        if (list === undefined) {
            return;
        }
        list.update_stream_name(stream_id, new_name);
    });
};

exports.update_user_full_name = function (user_id, full_name) {
    _.each([home_msg_list, message_list.narrowed, message_list.all], function (list) {
        if (list === undefined) {
            return;
        }
        list.update_user_full_name(user_id, full_name);
    });
};

exports.update_avatar = function (user_id, avatar_url) {
    var url = avatar_url;
    url = people.format_small_avatar_url(url);

    _.each([home_msg_list, message_list.narrowed, message_list.all], function (list) {
        if (list === undefined) {
            return;
        }
        list.update_user_avatar(user_id, url);
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = message_live_update;
}

window.message_live_update = message_live_update;

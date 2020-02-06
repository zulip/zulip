exports.update_stream_name = function (stream_id, new_name) {
    for (const list of [home_msg_list, message_list.narrowed, message_list.all]) {
        if (list === undefined) {
            continue;
        }
        list.update_stream_name(stream_id, new_name);
    }
};

exports.update_user_full_name = function (user_id, full_name) {
    for (const list of [home_msg_list, message_list.narrowed, message_list.all]) {
        if (list === undefined) {
            continue;
        }
        list.update_user_full_name(user_id, full_name);
    }
};

exports.update_avatar = function (user_id, avatar_url) {
    let url = avatar_url;
    url = people.format_small_avatar_url(url);

    for (const list of [home_msg_list, message_list.narrowed, message_list.all]) {
        if (list === undefined) {
            continue;
        }
        list.update_user_avatar(user_id, url);
    }
};

window.message_live_update = exports;

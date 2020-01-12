const IntDict = require('./int_dict').IntDict;

const away_user_ids = new Set();
const user_info = new IntDict();

exports.server_update = function (opts) {
    channel.post({
        url: '/json/users/me/status',
        data: {
            away: opts.away,
            status_text: opts.status_text,
        },
        idempotent: true,
        success: function () {
            if (opts.success) {
                opts.success();
            }
        },
    });
};

exports.server_set_away = function () {
    exports.server_update({away: true});
};

exports.server_revoke_away = function () {
    exports.server_update({away: false});
};

exports.set_away = function (user_id) {
    if (typeof user_id !== 'number') {
        blueslip.error('need ints for user_id');
    }
    away_user_ids.add(user_id);
};

exports.revoke_away = function (user_id) {
    if (typeof user_id !== 'number') {
        blueslip.error('need ints for user_id');
    }
    away_user_ids.delete(user_id);
};

exports.is_away = function (user_id) {
    return away_user_ids.has(user_id);
};

exports.get_status_text = function (user_id) {
    return user_info.get(user_id);
};

exports.set_status_text = function (opts) {
    if (!opts.status_text) {
        user_info.del(opts.user_id);
        return;
    }

    user_info.set(opts.user_id, opts.status_text);
};

exports.initialize = function () {
    _.each(page_params.user_status, function (dct, str_user_id) {
        // JSON does not allow integer keys, so we
        // convert them here.
        const user_id = parseInt(str_user_id, 10);

        if (dct.away) {
            away_user_ids.add(user_id);
        }

        if (dct.status_text) {
            user_info.set(user_id, dct.status_text);
        }
    });

    delete page_params.user_status;
};

window.user_status = exports;

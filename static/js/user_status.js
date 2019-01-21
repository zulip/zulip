var user_status = (function () {

var exports = {};

var away_user_ids = new Dict();

exports.server_set_away = function () {
    channel.post({
        url: '/json/users/me/status',
        data: {away: true},
        idempotent: true,
    });
};

exports.server_revoke_away = function () {
    channel.post({
        url: '/json/users/me/status',
        data: {away: false},
        idempotent: true,
    });
};

exports.set_away = function (user_id) {
    away_user_ids.set(user_id, true);
};

exports.revoke_away = function (user_id) {
    away_user_ids.del(user_id);
};

exports.is_away = function (user_id) {
    return away_user_ids.has(user_id);
};

exports.initialize = function () {
    _.each(page_params.user_status, function (dct, user_id) {
        if (dct.away) {
            away_user_ids.set(user_id, true);
        }
    });

    delete page_params.user_status;
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = user_status;
}
window.user_status = user_status;

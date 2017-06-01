var pm_conversations = (function () {

var exports = {};

var partners = new Dict();

exports.set_partner = function (user_id) {
    partners.set(user_id, true);
};

exports.is_partner = function (user_id) {
    return partners.get(user_id) || false;
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = pm_conversations;
}

var user_groups = (function () {

var exports = {};

var user_group_name_dict;
var user_group_by_id_dict;

// We have an init() function so that our automated tests
// can easily clear data.
exports.init = function () {
    user_group_name_dict = new Dict({fold_case: true});
    user_group_by_id_dict = new Dict();
};

// WE INITIALIZE DATA STRUCTURES HERE!
exports.init();

exports.add = function add(user_group) {
    user_group_name_dict.set(user_group.name, user_group);
    user_group_by_id_dict.set(user_group.id, user_group);
};

exports.get_user_group_from_id = function (group_id) {
    if (!user_group_by_id_dict.has(group_id)) {
        blueslip.error('Unknown group_id in get_user_group_from_id: ' + group_id);
        return undefined;
    }
    return user_group_by_id_dict.get(group_id);
};

exports.get_user_group_from_name = function (name) {
    return user_group_name_dict.get(name);
};

exports.get_realm_user_groups = function () {
    return user_group_name_dict.values();
};

exports.is_member_of = function (user_group_id, user_id) {
    var user_group = user_group_by_id_dict.get(user_group_id);
    return user_group.members.indexOf(user_id) !== -1;
};

exports.initialize = function () {
    _.each(page_params.realm_user_groups, function (user_group) {
        exports.add(user_group);
    });

    delete page_params.realm_user_groups; // We are the only consumer of this.
};

exports.is_user_group = function (item) {
    return item.hasOwnProperty('members');
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = user_groups;
}

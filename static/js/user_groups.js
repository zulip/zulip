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

exports.add = function (user_group) {
    // Reformat the user group members structure to be a dict.
    user_group.members = Dict.from_array(user_group.members);
    user_group_name_dict.set(user_group.name, user_group);
    user_group_by_id_dict.set(user_group.id, user_group);
};

exports.remove = function (user_group) {
    user_group_name_dict.del(user_group.name);
    user_group_by_id_dict.del(user_group.id);
};

exports.get_user_group_from_id = function (group_id) {
    if (!user_group_by_id_dict.has(group_id)) {
        blueslip.error('Unknown group_id in get_user_group_from_id: ' + group_id);
        return;
    }
    return user_group_by_id_dict.get(group_id);
};

exports.update = function (event) {
    var group = exports.get_user_group_from_id(event.group_id);
    if (event.data.name !== undefined) {
        group.name = event.data.name;
        user_group_name_dict.del(group.name);
        user_group_name_dict.set(group.name, group);
    }
    if (event.data.description !== undefined) {
        group.description = event.data.description;
        user_group_name_dict.del(group.name);
        user_group_name_dict.set(group.name, group);
    }
};

exports.get_user_group_from_name = function (name) {
    return user_group_name_dict.get(name);
};

exports.get_realm_user_groups = function () {
    return user_group_by_id_dict.values().sort(function (a, b) {
        return (a.id - b.id);
    });
};

exports.is_member_of = function (user_group_id, user_id) {
    var user_group = user_group_by_id_dict.get(user_group_id);
    return user_group.members.has(user_id);
};

exports.add_members = function (user_group_id, user_ids) {
    var user_group = user_group_by_id_dict.get(user_group_id);
    _.each(user_ids, function (user_id) {
        user_group.members.set(user_id, true);
    });
};

exports.remove_members = function (user_group_id, user_ids) {
    var user_group = user_group_by_id_dict.get(user_group_id);
    _.each(user_ids, function (user_id) {
        user_group.members.del(user_id);
    });
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

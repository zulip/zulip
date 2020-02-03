const FoldDict = require('./fold_dict').FoldDict;
const IntDict = require('./int_dict').IntDict;

let user_group_name_dict;
let user_group_by_id_dict;

// We have an init() function so that our automated tests
// can easily clear data.
exports.init = function () {
    user_group_name_dict = new FoldDict();
    user_group_by_id_dict = new IntDict();
};

// WE INITIALIZE DATA STRUCTURES HERE!
exports.init();

exports.add = function (user_group) {
    // Reformat the user group members structure to be a set.
    user_group.members = new Set(user_group.members);
    user_group_name_dict.set(user_group.name, user_group);
    user_group_by_id_dict.set(user_group.id, user_group);
};

exports.remove = function (user_group) {
    user_group_name_dict.delete(user_group.name);
    user_group_by_id_dict.delete(user_group.id);
};

exports.get_user_group_from_id = function (group_id, suppress_errors) {
    if (!user_group_by_id_dict.has(group_id)) {
        if (suppress_errors === undefined) {
            blueslip.error('Unknown group_id in get_user_group_from_id: ' + group_id);
        }
        return;
    }
    return user_group_by_id_dict.get(group_id);
};

exports.update = function (event) {
    const group = exports.get_user_group_from_id(event.group_id);
    if (event.data.name !== undefined) {
        group.name = event.data.name;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }
    if (event.data.description !== undefined) {
        group.description = event.data.description;
        user_group_name_dict.delete(group.name);
        user_group_name_dict.set(group.name, group);
    }
};

exports.get_user_group_from_name = function (name) {
    return user_group_name_dict.get(name);
};

exports.get_realm_user_groups = function () {
    return [...user_group_by_id_dict.values()].sort(function (a, b) {
        return a.id - b.id;
    });
};

exports.is_member_of = function (user_group_id, user_id) {
    const user_group = user_group_by_id_dict.get(user_group_id);
    if (user_group === undefined) {
        blueslip.error("Could not find user group with ID " + user_group_id);
        return false;
    }
    return user_group.members.has(user_id);
};

exports.add_members = function (user_group_id, user_ids) {
    const user_group = user_group_by_id_dict.get(user_group_id);
    _.each(user_ids, function (user_id) {
        user_group.members.add(user_id);
    });
};

exports.remove_members = function (user_group_id, user_ids) {
    const user_group = user_group_by_id_dict.get(user_group_id);
    _.each(user_ids, function (user_id) {
        user_group.members.delete(user_id);
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

window.user_groups = exports;

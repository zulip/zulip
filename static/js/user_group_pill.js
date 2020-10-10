"use strict";

function display_pill(group) {
    return group.name + ": " + group.members.size + " users";
}

exports.create_item_from_group_name = function (group_name, current_items) {
    group_name = group_name.trim();
    const group = user_groups.get_user_group_from_name(group_name);
    if (!group) {
        return undefined;
    }

    const existing_ids = current_items.map((item) => item.group_id);
    if (existing_ids.includes(group.id)) {
        return undefined;
    }

    const item = {
        display_value: display_pill(group),
        group_id: group.id,
        group_name: group.name,
    };

    return item;
};

exports.get_group_name_from_item = function (item) {
    return item.group_name;
};

function get_user_ids_from_user_groups(items) {
    let user_ids = [];
    const group_ids = items.map((item) => item.group_id).filter(Boolean);
    for (const group_id of group_ids) {
        const user_group = user_groups.get_user_group_from_id(group_id);
        user_ids = user_ids.concat(Array.from(user_group.members));
    }
    return user_ids;
}

exports.get_user_ids = function (pill_widget) {
    const items = pill_widget.items();
    let user_ids = get_user_ids_from_user_groups(items);
    user_ids = Array.from(new Set(user_ids));

    user_ids = user_ids.filter(Boolean);
    return user_ids;
};

exports.append_user_group = function (group, pill_widget) {
    pill_widget.appendValidatedData({
        display_value: display_pill(group),
        group_id: group.id,
        group_name: group.name,
    });
    pill_widget.clear_text();
};

exports.get_user_group_ids = function (pill_widget) {
    const items = pill_widget.items();
    let group_ids = items.map((item) => item.group_id);
    group_ids = group_ids.filter(Boolean);

    return group_ids;
};

exports.filter_taken_user_groups = function (items, pill_widget) {
    const taken_group_ids = exports.get_user_group_ids(pill_widget);

    items = items.filter((item) => !taken_group_ids.includes(item.id));
    return items;
};

exports.typeahead_source = function (pill_widget) {
    const potential_groups = user_groups.get_realm_user_groups();
    return exports.filter_taken_user_groups(potential_groups, pill_widget);
};

window.user_group_pill = exports;

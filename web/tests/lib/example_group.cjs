"use strict";

let last_issued_group_id = 20000;

const get_group_id = () => {
    last_issued_group_id += 1 + Math.floor(Math.random() * 10);
    return last_issued_group_id;
};

exports.make_user_group = (opts = {}) => {
    const id = opts.id ?? get_group_id();

    return {
        description: "Dummy user group",
        id,
        creator_id: 1,
        date_created: null,
        name: "Example user group",
        members: [],
        is_system_group: false,
        direct_subgroup_ids: [],
        can_add_members_group: 0,
        can_join_group: 0,
        can_leave_group: 0,
        can_manage_group: 0,
        can_mention_group: 0,
        can_remove_members_group: 0,
        deactivated: false,
        ...opts,
    };
};

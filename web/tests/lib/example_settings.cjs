"use strict";

exports.server_supported_permission_settings = {
    stream: {
        can_add_subscribers_group: {
            require_system_group: false,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
            default_group_name: "role:nobody",
            allowed_system_groups: [],
        },
        can_administer_channel_group: {
            require_system_group: true,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
            default_group_name: "stream_creator_or_nobody",
            allowed_system_groups: [],
        },
        can_remove_subscribers_group: {
            require_system_group: true,
            allow_internet_group: false,
            allow_nobody_group: false,
            allow_everyone_group: true,
            default_group_name: "role:administrators",
            allowed_system_groups: [],
        },
        can_subscribe_group: {
            require_system_group: false,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
            default_group_name: "role:nobody",
            allowed_system_groups: [],
        },
        can_resolve_topics_group: {
            require_system_group: false,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: true,
            default_group_name: "role:nobody",
            allowed_system_groups: [],
        },
    },
    realm: {
        create_multiuse_invite_group: {
            require_system_group: true,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
            default_group_name: "role:administrators",
            allowed_system_groups: [],
        },
        can_access_all_users_group: {
            require_system_group: true,
            allow_internet_group: false,
            allow_nobody_group: false,
            allow_everyone_group: true,
            default_group_name: "role:everyone",
            allowed_system_groups: ["role:everyone", "role:members"],
        },
        can_add_subscribers_group: {
            require_system_group: false,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
            default_group_name: "role:members",
            allowed_system_groups: [],
        },
    },
    group: {
        can_manage_group: {
            require_system_group: false,
            allow_internet_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
            default_group_name: "role:nobody",
            allowed_system_groups: [],
        },
    },
};

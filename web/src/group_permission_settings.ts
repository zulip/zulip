type GroupPermissionSetting = {
    require_system_group: boolean;
    allow_internet_group: boolean;
    allow_owners_group: boolean;
    allow_nobody_group: boolean;
    allow_everyone_group: boolean;
};

const group_permission_config_dict = new Map<string, GroupPermissionSetting>([
    [
        "can_remove_subscribers_group",
        {
            require_system_group: true,
            allow_internet_group: false,
            allow_owners_group: false,
            allow_nobody_group: false,
            allow_everyone_group: true,
        },
    ],
    [
        "create_multiuse_invite_group",
        {
            require_system_group: true,
            allow_internet_group: false,
            allow_owners_group: false,
            allow_nobody_group: true,
            allow_everyone_group: false,
        },
    ],
]);

export function get_group_permission_setting_config(
    setting_name: string,
): GroupPermissionSetting | undefined {
    const permission_config_dict = group_permission_config_dict.get(setting_name);
    if (!permission_config_dict) {
        throw new Error(`Invalid setting: ${setting_name}`);
    }
    return permission_config_dict;
}

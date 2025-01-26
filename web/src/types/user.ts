// Define user role constants
export const ROLE_REALM_OWNER = 100;
export const ROLE_REALM_ADMINISTRATOR = 200;
export const ROLE_MODERATOR = 300;
export const ROLE_MEMBER = 400;
export const ROLE_GUEST = 600;

export type UserProfile = {
    id: number;
    role: number;
    name: string;
    email: string;
};

/**
 * Function to check if a group ID corresponds to a role-based system group.
 * @param group_id - The ID of the group to check.
 * @returns True if the group ID is a role-based system group, otherwise false.
 */
export function is_role_based_system_group(group_id: number): boolean {
    const roleBasedSystemGroupIds = [
        ROLE_REALM_OWNER,
        ROLE_REALM_ADMINISTRATOR,
        ROLE_MODERATOR,
        ROLE_MEMBER,
        ROLE_GUEST,
    ];
    return roleBasedSystemGroupIds.includes(group_id);
}

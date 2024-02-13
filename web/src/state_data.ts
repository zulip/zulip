export let current_user: {
    avatar_source: string;
    delivery_email: string;
    is_admin: boolean;
    is_billing_admin: boolean;
    is_guest: boolean;
    is_moderator: boolean;
    is_owner: boolean;
    user_id: number;
};

export function set_current_user(initial_current_user: typeof current_user): void {
    current_user = initial_current_user;
}

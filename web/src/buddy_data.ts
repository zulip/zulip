
export function get_user_circle_class(user_id: number, is_deactivated: boolean): string {
    // Return class based on user status
    if (is_deactivated) {
        return "user-circle-offline";
    }

    // For demo, we can alternate active/idle based on even/odd user_id
    if (user_id % 2 === 0) {
        return "user-circle-active";
    } else {
        return "user-circle-idle";
    }
}
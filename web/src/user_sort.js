export function compare_a_b(a, b) {
    if (a > b) {
        return 1;
    } else if (a === b) {
        return 0;
    }
    return -1;
}

export function sort_email(a, b) {
    const email_a = a.delivery_email;
    const email_b = b.delivery_email;

    if (email_a === null && email_b === null) {
        // If both the emails are hidden, we sort the list by name.
        return compare_a_b(a.full_name.toLowerCase(), b.full_name.toLowerCase());
    }

    if (email_a === null) {
        // User with hidden should be at last.
        return 1;
    }
    if (email_b === null) {
        // User with hidden should be at last.
        return -1;
    }
    return compare_a_b(email_a.toLowerCase(), email_b.toLowerCase());
}

export function sort_role(a, b) {
    return compare_a_b(a.role, b.role);
}

export function sort_user_id(a, b) {
    return compare_a_b(a.user_id, b.user_id);
}

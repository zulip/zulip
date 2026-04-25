type UserLike = {
    delivery_email?: string | null;
    email?: string | null;
};

function normalize_email(value: string | null | undefined): string {
    return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function resolve_assignee_email(user: UserLike): string {
    const delivery_email = normalize_email(user.delivery_email);
    if (delivery_email !== "") {
        return delivery_email;
    }

    return normalize_email(user.email);
}

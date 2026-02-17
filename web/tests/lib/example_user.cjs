"use strict";

let last_issued_user_id = 1000;

const get_user_id = () => {
    last_issued_user_id += 1 + Math.floor(Math.random() * 100);
    return last_issued_user_id;
};

const Role = Object.freeze({
    OWNER: 100,
    ADMINISTRATOR: 200,
    MODERATOR: 300,
    MEMBER: 400,
    GUEST: 600,
});

const Bot = Object.freeze({
    GENERIC: 1,
    INCOMING_WEBHOOK: 2,
    OUTGOING_WEBHOOK: 3,
    EMBEDDED: 4,
});

const bot_or_user_props = (opts = {}) => {
    // Since other fields need `user_id`, we extract it early.
    const user_id = opts.user_id ?? get_user_id();
    const role = opts.role ?? Role.MEMBER;

    const common_props = {
        user_id,
        delivery_email: opts.delivery_email ?? null,
        email: `user-${user_id}@example.org`,
        full_name: `user-${user_id}-ex_name`,
        date_joined: Date.now(),
        // Derived from role, matching people._add_user() production logic.
        is_owner: role === Role.OWNER,
        is_admin: role === Role.OWNER || role === Role.ADMINISTRATOR,
        is_guest: role === Role.GUEST,
        is_moderator: role === Role.OWNER || role === Role.ADMINISTRATOR || role === Role.MODERATOR,
        timezone: "UTC",
        avatar_version: 0,
        role,
    };

    return {...common_props, ...opts};
};

const make_user = (opts = {}) => ({
    ...bot_or_user_props(opts),
    is_bot: false,
    // By default an empty dictionary.
    profile_data: opts.profile_data ?? {},
});

const make_bot = (opts = {}) => ({
    ...bot_or_user_props(opts),
    is_bot: true,
    // By default a generic bot.
    bot_type: opts.bot_type ?? Bot.GENERIC,
    bot_owner_id: opts.bot_owner_id ?? null,
});

const make_cross_realm_bot = (opts = {}) => ({
    ...make_bot(opts),
    is_system_bot: true,
});

exports.make_bot = make_bot;
exports.make_user = make_user;
exports.make_cross_realm_bot = make_cross_realm_bot;
exports.Role = Role;
exports.Bot = Bot;

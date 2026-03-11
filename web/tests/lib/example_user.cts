import type * as z_types from "zod/mini";
import type {user_schema as user_schema_type} from "../../src/state_data";

const {user_schema} = require("../../src/state_data") as {user_schema: typeof user_schema_type};

export type User = z_types.output<typeof user_schema>;

let last_issued_user_id = 1000;

const get_user_id = () => {
    last_issued_user_id += 1 + Math.floor(Math.random() * 100);
    return last_issued_user_id;
};

const Role = {
    OWNER: 100,
    ADMINISTRATOR: 200,
    MODERATOR: 300,
    MEMBER: 400,
    GUEST: 600,
} as const;

const Bot = {
    GENERIC: 1,
    INCOMING_WEBHOOK: 2,
    OUTGOING_WEBHOOK: 3,
    EMBEDDED: 4,
} as const;

type UserOptions = Partial<User> & {
    bot_owner_id?: number | null;
    bot_type?: number | null;
};

const bot_or_user_props = (opts: UserOptions) => {
    // Since other fields need `user_id`, we extract it early.
    const user_id = opts.user_id ?? get_user_id();
    const role = opts.role ?? Role.MEMBER;

    const common_props = {
        user_id,
        delivery_email: opts.delivery_email ?? null,
        email: `user-${user_id}@example.org`,
        full_name: `user-${user_id}-ex_name`,
        date_joined: "2024-01-01T00:00:00Z",
        // Derived from role, matching people._add_user() production logic.
        is_owner: role === Role.OWNER,
        is_admin: role === Role.OWNER || role === Role.ADMINISTRATOR,
        is_guest: role === Role.GUEST,
        is_moderator: role === Role.OWNER || role === Role.ADMINISTRATOR || role === Role.MODERATOR,
        timezone: "UTC",
        avatar_version: 0,
        is_imported_stub: opts.is_imported_stub ?? false,
        role,
    };

    return {...common_props, ...opts};
};

const make_user = (opts: UserOptions = {}): User => {
    if (opts.is_bot) {
        return make_bot(opts);
    }
    return {
    ...bot_or_user_props(opts),
    is_bot: false,
    bot_type: undefined,
    // By default an empty dictionary.
    profile_data: opts.profile_data ?? {},
    } as User;
};

const make_bot = (opts: UserOptions = {}): User => ({
    ...bot_or_user_props(opts),
    is_bot: true,
    // By default a generic bot.
    bot_type: opts.bot_type ?? Bot.GENERIC,
    bot_owner_id: opts.bot_owner_id ?? null,
} as User);

const make_cross_realm_bot = (opts: UserOptions = {}): User => ({
    ...make_bot(opts),
    is_system_bot: true,
} as User);

module.exports = {
    make_bot,
    make_user,
    make_cross_realm_bot,
    Role,
    Bot,
};

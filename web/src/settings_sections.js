import * as alert_words_ui from "./alert_words_ui";
import * as attachments_ui from "./attachments_ui";
import * as blueslip from "./blueslip";
import * as settings_account from "./settings_account";
import * as settings_bots from "./settings_bots";
import * as settings_display from "./settings_display";
import * as settings_emoji from "./settings_emoji";
import * as settings_exports from "./settings_exports";
import * as settings_invites from "./settings_invites";
import * as settings_linkifiers from "./settings_linkifiers";
import * as settings_muted_users from "./settings_muted_users";
import * as settings_notifications from "./settings_notifications";
import * as settings_org from "./settings_org";
import * as settings_playgrounds from "./settings_playgrounds";
import * as settings_profile_fields from "./settings_profile_fields";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults";
import * as settings_streams from "./settings_streams";
import * as settings_user_groups from "./settings_user_groups_legacy";
import * as settings_user_topics from "./settings_user_topics";
import * as settings_users from "./settings_users";

const load_func_dict = new Map(); // group -> function
const loaded_groups = new Set();

export function get_group(section) {
    // Sometimes several sections all share the same code.

    switch (section) {
        case "organization-profile":
        case "organization-settings":
        case "organization-permissions":
        case "auth-methods":
            return "org_misc";

        case "bot-list-admin":
            return "org_bots";

        case "user-list-admin":
        case "deactivated-users-admin":
            return "org_users";

        case "profile":
        case "account-and-privacy":
            return "your-account";

        default:
            return section;
    }
}

export function initialize() {
    // personal
    load_func_dict.set("your-account", settings_account.set_up);
    load_func_dict.set("preferences", () => {
        settings_display.set_up(settings_display.user_settings_panel);
    });
    load_func_dict.set("notifications", () => {
        settings_notifications.set_up(settings_notifications.user_settings_panel);
    });
    load_func_dict.set("your-bots", settings_bots.set_up);
    load_func_dict.set("alert-words", alert_words_ui.set_up_alert_words);
    load_func_dict.set("uploaded-files", attachments_ui.set_up_attachments);
    load_func_dict.set("topics", settings_user_topics.set_up);
    load_func_dict.set("muted-users", settings_muted_users.set_up);

    // org
    load_func_dict.set("org_misc", settings_org.set_up);
    load_func_dict.set("org_bots", settings_users.set_up_bots);
    load_func_dict.set("org_users", settings_users.set_up_humans);
    load_func_dict.set("emoji-settings", settings_emoji.set_up);
    load_func_dict.set("default-streams-list", settings_streams.set_up);
    load_func_dict.set("linkifier-settings", settings_linkifiers.set_up);
    load_func_dict.set("playground-settings", settings_playgrounds.set_up);
    load_func_dict.set("invites-list-admin", settings_invites.set_up);
    load_func_dict.set("user-groups-admin", settings_user_groups.set_up);
    load_func_dict.set("profile-field-settings", settings_profile_fields.set_up);
    load_func_dict.set("data-exports-admin", settings_exports.set_up);
    load_func_dict.set(
        "organization-level-user-defaults",
        settings_realm_user_settings_defaults.set_up,
    );
}

export function load_settings_section(section) {
    const group = get_group(section);

    if (!load_func_dict.has(group)) {
        blueslip.error("Unknown section " + section);
        return;
    }

    if (loaded_groups.has(group)) {
        // We only load groups once (unless somebody calls
        // reset_sections).
        return;
    }

    const load_func = load_func_dict.get(group);

    // Do the real work here!
    load_func();
    loaded_groups.add(group);
}

export function reset_sections() {
    loaded_groups.clear();
    settings_emoji.reset();
    settings_exports.reset();
    settings_linkifiers.reset();
    settings_playgrounds.reset();
    settings_invites.reset();
    settings_org.reset();
    settings_profile_fields.reset();
    settings_streams.reset();
    settings_user_groups.reset();
    settings_user_topics.reset();
    settings_muted_users.reset();
    alert_words_ui.reset();
    // settings_users doesn't need a reset()
}

import _ from "lodash";

import * as blueslip from "./blueslip";
import * as compose_state from "./compose_state";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as muted_users from "./muted_users";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as presence from "./presence";
import * as stream_data from "./stream_data";
import * as timerender from "./timerender";
import * as unread from "./unread";
import * as user_status from "./user_status";
import * as util from "./util";

/*

   This is the main model code for building the buddy list.
   We also rely on presence.js to compute the actual presence
   for users.  We glue in other "people" data and do
   filtering/sorting of the data that we'll send into the view.

*/

export const max_size_before_shrinking = 600;

export function get_user_circle_class(user_id) {
    const status = buddy_status(user_id);

    switch (status) {
        case "active":
            return "user_circle_green";
        case "idle":
            return "user_circle_idle";
        case "away_them":
        case "away_me":
            return "user_circle_empty_line";
        default:
            return "user_circle_empty";
    }
}

export function status_description(user_id) {
    const status = buddy_status(user_id);

    switch (status) {
        case "active":
            return $t({defaultMessage: "Active"});
        case "idle":
            return $t({defaultMessage: "Idle"});
        case "away_them":
        case "away_me":
            return $t({defaultMessage: "Unavailable"});
        default:
            return $t({defaultMessage: "Offline"});
    }
}

export function level(user_id) {
    if (people.is_my_user_id(user_id)) {
        // Always put current user at the top.
        return 0;
    }

    const status = buddy_status(user_id);

    switch (status) {
        case "active":
            return 1;
        case "idle":
            return 2;
        case "away_them":
            return 3;
        default:
            return 3;
    }
}

export function buddy_status(user_id) {
    if (user_status.is_away(user_id)) {
        if (people.is_my_user_id(user_id)) {
            return "away_me";
        }

        return "away_them";
    }

    // get active/idle/etc.
    return presence.get_status(user_id);
}

export function compare_function(a, b) {
    const level_a = level(a);
    const level_b = level(b);
    const diff = level_a - level_b;
    if (diff !== 0) {
        return diff;
    }

    // Sort equivalent PM names alphabetically
    const person_a = people.get_by_user_id(a);
    const person_b = people.get_by_user_id(b);

    const full_name_a = person_a ? person_a.full_name : "";
    const full_name_b = person_b ? person_b.full_name : "";

    return util.strcmp(full_name_a, full_name_b);
}

export function sort_users(user_ids) {
    // TODO sort by unread count first, once we support that
    user_ids.sort(compare_function);
    return user_ids;
}

function get_num_unread(user_id) {
    return unread.num_unread_for_person(user_id.toString());
}

export function get_my_user_status(user_id) {
    if (!people.is_my_user_id(user_id)) {
        return undefined;
    }

    if (user_status.is_away(user_id)) {
        return $t({defaultMessage: "(unavailable)"});
    }

    return $t({defaultMessage: "(you)"});
}

export function user_last_seen_time_status(user_id) {
    const status = presence.get_status(user_id);
    if (status === "active") {
        return $t({defaultMessage: "Active now"});
    }

    if (status === "idle") {
        // When we complete our presence API rewrite to have the data
        // plumbed, we may want to change this to also mention when
        // they were last active.
        return $t({defaultMessage: "Idle"});
    }

    const last_active_date = presence.last_active_date(user_id);
    let last_seen;
    if (page_params.realm_is_zephyr_mirror_realm) {
        // We don't send presence data to clients in Zephyr mirroring realms
        last_seen = $t({defaultMessage: "Unknown"});
    } else if (last_active_date === undefined) {
        // There are situations where the client has incomplete presence
        // history on a user.  This can happen when users are deactivated,
        // or when they just haven't been present in a long time (and we
        // may have queries on presence that go back only N weeks).
        //
        // We give this vague status for such users; we will get to
        // delete this code when we finish rewriting the presence API.
        last_seen = $t({defaultMessage: "More than 2 weeks ago"});
    } else {
        last_seen = timerender.last_seen_status_from_date(last_active_date);
    }
    return $t({defaultMessage: "Last active: {last_seen}"}, {last_seen});
}

export function info_for(user_id) {
    const user_circle_class = get_user_circle_class(user_id);
    const person = people.get_by_user_id(user_id);
    const my_user_status = get_my_user_status(user_id);

    const status_emoji_info = user_status.get_status_emoji(user_id);
    const user_circle_status = status_description(user_id);

    return {
        href: hash_util.pm_with_url(person.email),
        name: person.full_name,
        user_id,
        my_user_status,
        status_emoji_info,
        is_current_user: people.is_my_user_id(user_id),
        num_unread: get_num_unread(user_id),
        user_circle_class,
        user_circle_status,
    };
}

export function get_title_data(user_ids_string, is_group) {
    if (is_group === true) {
        // For groups, just return a string with recipient names.
        return {
            first_line: people.get_recipients(user_ids_string),
            second_line: "",
            third_line: "",
        };
    }

    // Since it's not a group, user_ids_string is a single user ID.
    const user_id = Number.parseInt(user_ids_string, 10);
    const person = people.get_by_user_id(user_id);

    if (person.is_bot) {
        const bot_owner = people.get_bot_owner_user(person);

        if (bot_owner) {
            const bot_owner_name = $t(
                {defaultMessage: "Owner: {name}"},
                {name: bot_owner.full_name},
            );

            return {
                first_line: person.full_name,
                second_line: bot_owner_name,
                third_line: "",
            };
        }

        // Bot does not have an owner.
        return {
            first_line: person.full_name,
            second_line: "",
            third_line: "",
        };
    }

    // For buddy list and individual PMS.  Since is_group=False, it's
    // a single, human, user.
    const last_seen = user_last_seen_time_status(user_id);
    const is_my_user = people.is_my_user_id(user_id);

    // Users has a status.
    if (user_status.get_status_text(user_id)) {
        return {
            first_line: person.full_name,
            second_line: user_status.get_status_text(user_id),
            third_line: last_seen,
            show_you: is_my_user,
        };
    }

    // Users does not have a status.
    return {
        first_line: person.full_name,
        second_line: last_seen,
        third_line: "",
        show_you: is_my_user,
    };
}

export function get_item(user_id) {
    const info = info_for(user_id);
    return info;
}

export function get_items_for_people(ids) {
    const info = ids.map((id) => info_for(id));
    return info;
}

function user_is_recently_active(user_id) {
    // return true if the user has a green/orange circle
    return level(user_id) <= 2;
}

function maybe_shrink_list(ids, filter_text) {
    if (ids.length <= max_size_before_shrinking) {
        return {ids, is_shrunk: false};
    }

    if (filter_text) {
        // If the user types something, we want to show all
        // users matching the text, even if they have not been
        // online recently.
        // For super common letters like "s", we may
        // eventually want to filter down to only users that
        // are in presence.get_ids().
        return {ids, is_shrunk: false};
    }

    // We have to partition and can't just directly slice ids here
    // because we want to make sure we include all recently_active
    // users (and no one has guaranteed those are at the start)
    const [recently_active_ids, offline_ids] = _.partition(ids, user_is_recently_active);
    if (recently_active_ids.length < max_size_before_shrinking) {
        return {
            ids: [
                ...recently_active_ids,
                ...offline_ids.slice(0, max_size_before_shrinking - recently_active_ids.length),
            ],
            is_shrunk: true,
        };
    }
    // else
    return {ids: recently_active_ids, is_shrunk: true};
}

function filter_ids(filter_text, user_ids) {
    // This first filter is for whether the user is eligible to be
    // displayed in the right sidebar at all.
    user_ids = user_ids.filter((user_id) => {
        const person = people.get_by_user_id(user_id);

        if (!person) {
            blueslip.warn("Got user_id in presence but not people: " + user_id);
            return false;
        }

        if (person.is_bot) {
            // Bots should never appear in the right sidebar.  This
            // case should never happen, since bots cannot have
            // presence data.
            return false;
        }

        if (muted_users.is_user_muted(user_id)) {
            // Muted users are hidden from the right sidebar entirely.
            return false;
        }

        return true;
    });

    if (!filter_text) {
        return user_ids;
    }

    // If a query is present in "Search people", we return matches.
    user_ids = user_ids.filter((user_id) => !people.is_my_user_id(user_id));

    let search_terms = filter_text.toLowerCase().split(/[,|]+/);
    search_terms = search_terms.map((s) => s.trim());

    const persons = user_ids.map((user_id) => people.get_by_user_id(user_id));

    const user_id_dict = people.filter_people_by_search_terms(persons, search_terms);

    return Array.from(user_id_dict.keys());
}

function get_filtered_all_user_id_list(filter_text) {
    let base_user_id_list;

    if (filter_text) {
        // If there's a filter, select from all users, not just those
        // recently active.
        base_user_id_list = people.get_active_user_ids();
    } else {
        // From large realms, the user_ids in presence may exclude
        // users who have been idle more than three weeks.  When the
        // filter text is blank, we show only those recently active users.
        base_user_id_list = presence.get_user_ids();

        // Always include ourselves, even if we're "unavailable".
        const my_user_id = people.my_current_user_id();
        if (!base_user_id_list.includes(my_user_id)) {
            base_user_id_list = [my_user_id, ...base_user_id_list];
        }
    }

    const user_ids = filter_ids(filter_text, base_user_id_list);
    return user_ids;
}

function get_user_id_list_and_title_for_narrow_state(narrow_filter) {
    if (narrow_state.stream()) {
        if (!narrow_state.stream_sub()) {
            // eg if we're narrowed to a stream that does not exist.
            return {
                user_ids: [],
                user_title: $t({defaultMessage: "In #Unknown Stream"}),
            };
        }
        // else
        return {
            user_ids: get_stream_recipients_list(narrow_state.stream_sub().stream_id),
            user_title: $t(
                {defaultMessage: "In #{streamName}"},
                {streamName: narrow_state.stream_sub().name},
            ),
        };
    } else if (narrow_filter.has_operator("pm-with")) {
        return {
            user_ids: get_pm_recipients_list(narrow_filter.operands("pm-with")[0].split(",")),
            user_title: $t({defaultMessage: "In selected conversation"}),
        };
    }
    // else
    return {};
}

function get_user_id_list_and_title_for_private_message(private_message_recipient) {
    return {
        user_ids: get_pm_recipients_list(private_message_recipient.split(",")),
        user_title: $t({defaultMessage: "PM recipients"}),
    };
}

function get_user_id_list_and_title_for_stream_message(stream_name) {
    const stream = stream_data.get_sub_by_name(stream_name);
    let user_ids = [];
    if (stream) {
        user_ids = get_stream_recipients_list(stream.stream_id);
    }
    return {
        user_ids,
        user_title: $t({defaultMessage: "In #{streamName}"}, {streamName: stream_name}),
    };
}

function get_pm_recipients_list(user_emails) {
    const user_ids = _.reduce(
        user_emails,
        (list, user_email) => {
            if (people.is_valid_email_for_compose(user_email)) {
                const user_id = people.get_user_id(user_email);
                const person = people.get_by_user_id(user_id);
                // if the user is bot, do not show in right sidebar.
                if (person && !person.is_bot) {
                    list.push(user_id);
                }
                return list;
            }
            return list;
        },
        [],
    );

    // Add current user to buddy list
    const me = people.my_current_user_id();
    if (!_.includes(user_ids, me)) {
        user_ids.push(me);
    }

    return user_ids;
}

function get_stream_recipients_list(stream_id) {
    let user_ids = people.get_active_user_ids();
    user_ids = _.filter(user_ids, (user_id) => {
        const person = people.get_by_user_id(user_id);
        if (
            person && // if the user is bot, do not show in right sidebar.
            person.is_bot
        ) {
            return false;
        }
        if (stream_id && !stream_data.is_user_subscribed(stream_id, person.user_id)) {
            return false;
        }
        return true;
    });
    return user_ids;
}

function get_user_id_list_for_compose() {
    let users = {};
    const stream_name = compose_state.stream_name();
    // if compose stream matches narrow stream, we display title based on narrow.
    if (stream_name && !(stream_name === narrow_state.stream())) {
        users = get_user_id_list_and_title_for_stream_message(stream_name);
    }
    const private_message_recipient = compose_state.private_message_recipient();
    if (private_message_recipient) {
        users = get_user_id_list_and_title_for_private_message(private_message_recipient);
    }
    return users;
}

function filter_and_shrink_and_sort_user_ids(filter_text, users) {
    users.user_ids = filter_ids(filter_text, users.user_ids);
    return shrink_and_sort_user_ids(filter_text, users);
}

function shrink_and_sort_user_ids(filter_text, users) {
    const maybe_shrunk_list = maybe_shrink_list(users.user_ids, filter_text);
    if (maybe_shrunk_list.is_shrunk) {
        return {
            user_ids: sort_users(maybe_shrunk_list.ids),
            user_title: users.user_title,
            unshrunk_user_ids: users.user_ids,
        };
    }
    // else
    return {user_ids: sort_users(users.user_ids), user_title: users.user_title};
}

function get_processed_users_section_data(filter_text) {
    const narrow_filter = narrow_state.filter();
    if (compose_state.composing()) {
        const users = get_user_id_list_for_compose();
        if (users.user_title) {
            return filter_and_shrink_and_sort_user_ids(filter_text, users);
        }
    }
    if (narrow_filter) {
        const users = get_user_id_list_and_title_for_narrow_state(narrow_filter);
        if (users.user_title) {
            return filter_and_shrink_and_sort_user_ids(filter_text, users);
        }
    }
    // show all users list
    const users = {
        user_ids: get_filtered_all_user_id_list(filter_text),
    };
    return shrink_and_sort_user_ids(filter_text, users);
}

function get_processed_others_section_data(filter_text, user_ids) {
    const all_user_ids = get_filtered_all_user_id_list(filter_text);
    const other_ids = all_user_ids.filter(
        (potential_other_id) => !user_ids.includes(potential_other_id),
    );

    let other_title;
    if (other_ids.length) {
        other_title = $t({defaultMessage: "All other users"});
        const maybe_shrunk_list = maybe_shrink_list(other_ids, filter_text);
        if (maybe_shrunk_list.is_shrunk) {
            return {
                other_ids: sort_users(maybe_shrunk_list.ids),
                other_title,
                unshrunk_other_ids: other_ids,
            };
        }
        return {other_ids: sort_users(other_ids), other_title};
    }
    // else
    return {
        other_ids: [],
    };
}

// Please ensure that changes to get_filtered_and_sorted_key_groups_and_titles
// are consistent with changes to does_belong_to_users_or_others_section
export function get_filtered_and_sorted_key_groups_and_titles(filter_text) {
    const users = get_processed_users_section_data(filter_text);
    let key_groups_and_titles = {
        user_keys: users.user_ids,
        other_keys: [],
    };
    let user_ids;
    if (users.unshrunk_user_ids) {
        user_ids = users.unshrunk_user_ids;
        key_groups_and_titles.extra_users_count =
            users.unshrunk_user_ids.length - users.user_ids.length;
    } else {
        user_ids = users.user_ids;
    }
    // if there's no user title, we're looking at the all users list,
    // so there's no others section.
    if (users.user_title) {
        const others = get_processed_others_section_data(filter_text, user_ids);
        key_groups_and_titles = {
            ...key_groups_and_titles,
            user_keys_title: users.user_title,
            other_keys: others.other_ids,
            other_keys_title: others.other_title,
        };
        if (others.unshrunk_other_ids) {
            key_groups_and_titles.extra_others_count =
                others.unshrunk_other_ids.length - others.other_ids.length;
        }
    }
    return key_groups_and_titles;
}

// this function essentially replicates the logic to answer does user
// belong to the users section or the others section from
// get_filtered_and_sorted_key_groups_and_titles but is different in
// that it is meant for only one user and as such is faster.
//
// Please ensure that changes to does_belong_to_users_or_others_section
// are consistent with changes to get_filtered_and_sorted_key_groups_and_titles
export function does_belong_to_users_or_others_section(user_id) {
    if (compose_state.composing()) {
        const stream_name = compose_state.stream_name();
        if (stream_name) {
            const is_subscriber = stream_data
                .get_subscribed_streams_for_user(user_id)
                .map((stream) => stream.name.toLowerCase())
                .includes(stream_name.toLowerCase());
            if (is_subscriber) {
                return "users";
            }
            return "others";
        }
        const private_message_recipient = compose_state.private_message_recipient();
        if (private_message_recipient) {
            const is_recipient = private_message_recipient
                .split(",")
                .includes(people.get_by_user_id(user_id).email);
            if (is_recipient) {
                return "users";
            }
            return "others";
        }
        blueslip.error("compose_state composing but not stream or private_message");
        return "users";
    }

    const filter = narrow_state.filter();
    if (!filter) {
        return "users";
    }

    if (narrow_state.stream()) {
        const stream_name = narrow_state.stream_sub().name;
        const is_subscriber = stream_data
            .get_subscribed_streams_for_user(user_id)
            .map((stream) => stream.name)
            .includes(stream_name);
        if (is_subscriber) {
            return "users";
        }
        return "others";
    } else if (filter.has_operator("pm-with")) {
        const is_recipient = filter
            .operands("pm-with")[0]
            .split(",")
            .includes(people.get_by_user_id(user_id).email);
        if (is_recipient) {
            return "users";
        }
        return "others";
    }

    return "users";
}

export function matches_filter(filter_text, user_id) {
    // This is a roundabout way of checking a user if you look
    // too hard at it, but it should be fine for now.
    return filter_ids(filter_text, [user_id]).length === 1;
}

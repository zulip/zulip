import $ from "jquery";
import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";
import render_search_user_pill from "../templates/search_user_pill.hbs";

import {Filter} from "./filter.ts";
import * as input_pill from "./input_pill.ts";
import type {InputPill, InputPillContainer} from "./input_pill.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as user_status from "./user_status.ts";
import type {UserStatusEmojiInfo} from "./user_status.ts";
import * as util from "./util.ts";

export type SearchUserPill = {
    type: "search_user";
    operator: string;
    negated: boolean;
    users: {
        full_name: string;
        user_id: number;
        email: string;
        img_src: string;
        status_emoji_info: UserStatusEmojiInfo | undefined;
        should_add_guest_user_indicator: boolean;
        deactivated: boolean;
    }[];
    display_value?: string;
};

type SearchPill =
    | {
          type: "search";
          operator: string;
          operand: string;
          negated: boolean | undefined;
      }
    | SearchUserPill;

export type SearchPillWidget = InputPillContainer<SearchPill>;

export function create_item_from_search_string(search_string: string): SearchPill | undefined {
    const search_term = util.the(Filter.parse(search_string));
    if (!Filter.is_valid_search_term(search_term)) {
        // This will cause pill validation to fail and trigger a shake animation.
        return undefined;
    }
    return {
        type: "search",
        operator: search_term.operator,
        operand: search_term.operand,
        negated: search_term.negated,
    };
}

export function get_search_string_from_item(item: SearchPill): string {
    if (item.type === "search_user" && item.operator === "dm-including" && item.display_value) {
        return item.display_value;
    }
    const sign = item.negated ? "-" : "";
    return `${sign}${item.operator}: ${get_search_operand(item, true)}`;
}

// This is called when the a pill is closed. We have custom logic here
// because group user pills have pills inside of them, and it's possible
// to e.g. remove a user from a group-DM pill without deleting the whole
// DM pill.
function on_pill_exit(
    clicked_element: HTMLElement,
    all_pills: InputPill<SearchPill>[],
    remove_pill: (pill: HTMLElement) => void,
): void {
    const $user_pill_container = $(clicked_element).parents(".user-pill-container");
    if ($user_pill_container.length === 0) {
        // This is just a regular search pill, so we don't need to do fancy logic.
        const $clicked_pill = $(clicked_element).closest(".pill");
        remove_pill(util.the($clicked_pill));
        return;
    }
    // The user-pill-container container class is used exclusively for
    // group-DM search pills, where multiple user pills sit inside a larger
    // pill. The exit icons in those individual user pills should remove
    // just that pill, not the outer pill.
    const user_id_string = $(clicked_element).closest(".pill").attr("data-user-id");
    assert(user_id_string !== undefined);
    const user_id = Number.parseInt(user_id_string, 10);

    // First get the outer pill that contains the user pills.
    const outer_idx = all_pills.findIndex((pill) => pill.$element[0] === $user_pill_container[0]);
    assert(outer_idx !== -1);
    const user_container_pill = all_pills[outer_idx]!.item;
    assert(user_container_pill?.type === "search_user");

    // If there's only one user in this pill, delete the whole pill.
    if (user_container_pill.users.length === 1) {
        assert(util.the(user_container_pill.users).user_id === user_id);
        remove_pill(util.the($user_pill_container));
        return;
    }

    // Remove the user id from the pill data.
    const user_idx = user_container_pill.users.findIndex((user) => user.user_id === user_id);
    assert(user_idx !== -1);
    user_container_pill.users.splice(user_idx, 1);

    // Remove the user pill from the DOM.
    const $outer_container = all_pills[outer_idx]!.$element;
    const $user_pill = $($outer_container.children(".pill")[user_idx]!);
    assert($user_pill.attr("data-user-id") === user_id.toString());
    $user_pill.remove();
}

export function create_pills($pill_container: JQuery): SearchPillWidget {
    const pills = input_pill.create({
        $container: $pill_container,
        create_item_from_text: create_item_from_search_string,
        get_text_from_item: get_search_string_from_item,
        split_text_on_comma: false,
        convert_to_pill_on_enter: false,
        generate_pill_html(item) {
            if (item.type === "search_user") {
                return render_search_user_pill(item);
            }
            if (item.operator === "topic" && item.operand === "") {
                return render_input_pill({
                    is_empty_string_topic: true,
                    sign: item.negated ? "-" : "",
                    topic_display_name: util.get_final_topic_display_name(""),
                });
            }
            const display_value = get_search_string_from_item(item);
            return render_input_pill({
                display_value,
            });
        },
        get_display_value_from_item: get_search_string_from_item,
        on_pill_exit,
    });
    // We don't automatically create pills on paste. When the user
    // presses enter, we validate the input then.
    pills.createPillonPaste(() => false);
    return pills;
}

function append_user_pill(
    users: User[],
    pill_widget: SearchPillWidget,
    operator: string,
    negated: boolean,
): void {
    const valid_users = users.filter((user) => people.get_by_email(user.email));

    if (operator === "dm-including") {
        const existing_pill = pill_widget
            .items()
            .find(
                (item): item is SearchUserPill =>
                    item.type === "search_user" && item.operator === "dm-including",
            );

        if (existing_pill && valid_users.length === 1) {
            const existing_emails = new Set(existing_pill.users.map((u) => u.email));
            const new_users = valid_users.filter((u) => !existing_emails.has(u.email));
            if (new_users.length > 0) {
                const new_user_objs = new_users.map((u) => ({
                    full_name: u.full_name,
                    user_id: u.user_id,
                    email: u.email,
                    img_src: people.small_avatar_url_for_person(u),
                    status_emoji_info: user_status.get_status_emoji(u.user_id),
                    should_add_guest_user_indicator: people.should_add_guest_user_indicator(
                        u.user_id,
                    ),
                    deactivated: !people.is_person_active(u.user_id) && !u.is_inaccessible_user,
                }));
                existing_pill.users.push(...new_user_objs);

                // To remove the old pill from the widget.
                const items = pill_widget.items();
                const idx = items.indexOf(existing_pill);
                if (idx !== -1) {
                    items.splice(idx, 1);
                    pill_widget.clear();
                }

                pill_widget.appendValidatedData(existing_pill);
            }
            pill_widget.clear_text();
            return;
        }
    }

    if (operator === "dm-including") {
        const existing_emails = new Set(
            pill_widget
                .items()
                .filter((item) => item.type === "search_user")
                .flatMap((item: SearchUserPill) => item.users.map((user) => user.email)),
        );
        users = valid_users.filter((u) => !existing_emails.has(u.email));
    } else {
        users = valid_users;
    }

    const pill_data: SearchUserPill = {
        type: "search_user",
        operator,
        negated,
        users: users.map((user) => ({
            full_name: user.full_name,
            user_id: user.user_id,
            email: user.email,
            img_src: people.small_avatar_url_for_person(user),
            status_emoji_info: user_status.get_status_emoji(user.user_id),
            should_add_guest_user_indicator: people.should_add_guest_user_indicator(user.user_id),
            deactivated: !people.is_person_active(user.user_id) && !user.is_inaccessible_user,
        })),
    };

    pill_widget.appendValidatedData(pill_data);
    pill_widget.clear_text();
}

const user_pill_operators = new Set(["dm", "dm-including", "sender"]);

export function set_search_bar_contents(
    search_terms: NarrowTerm[],
    pill_widget: SearchPillWidget,
    set_search_bar_text: (text: string) => void,
): void {
    pill_widget.clear(true);
    let partial_pill = "";
    const invalid_inputs = [];
    const search_operator_strings = [];

    for (const term of search_terms) {
        const input = Filter.unparse([term]);

        // If the last term looks something like `dm:`, we
        // don't want to make it a pill, since it isn't isn't
        // a complete search term yet.
        // Instead, we keep the partial pill to the end of the
        // search box as text input, which will update the
        // typeahead to show operand suggestions.
        // Note: We make a pill for `topic:` as it represents empty string topic
        // except the case where it suggests `topic` operator.
        if (input.at(-1) === ":" && term.operand === "" && term === search_terms.at(-1)) {
            const is_topic_operator_suggestion = (): boolean => {
                const is_typeahead_visible = $("#searchbox_form .typeahead").is(":visible");
                return (
                    is_typeahead_visible &&
                    $("#searchbox_form .typeahead-item.active .empty-topic-display").length === 0
                );
            };
            if (term.operator !== "topic" || is_topic_operator_suggestion()) {
                partial_pill = input;
                continue;
            }
        }

        if (!Filter.is_valid_search_term(term)) {
            invalid_inputs.push(input);
            continue;
        }

        if (user_pill_operators.has(term.operator) && term.operand !== "") {
            const users = term.operand
                .split(",")
                .map((email) => people.get_by_email(email.trim())!);
            append_user_pill(users, pill_widget, term.operator, term.negated ?? false);
        } else if (term.operator === "search") {
            search_operator_strings.push(input);
        } else {
            pill_widget.appendValue(input);
        }
    }
    pill_widget.clear_text();

    const search_bar_text_strings = [...search_operator_strings, ...invalid_inputs];
    if (partial_pill !== "") {
        search_bar_text_strings.push(partial_pill);
    }
    set_search_bar_text(search_bar_text_strings.join(" "));
    if (invalid_inputs.length > 0) {
        $("#search_query").addClass("shake");
    }
}

function get_search_operand(item: SearchPill, for_display: boolean): string {
    if (item.type === "search_user") {
        return item.users.map((user) => user.email).join(",");
    }
    if (for_display && item.operator === "channel") {
        return stream_data.get_valid_sub_by_id_string(item.operand).name;
    }
    if (for_display && item.operator === "topic") {
        return util.get_final_topic_display_name(item.operand);
    }
    return item.operand;
}

export function get_current_search_pill_terms(pill_widget: SearchPillWidget): NarrowTerm[] {
    return pill_widget.items().map((item) => ({
        ...item,
        operand: get_search_operand(item, false),
    }));
}

import $ from "jquery";

import {Filter} from "./filter";
import * as input_pill from "./input_pill";
import type {InputPillContainer} from "./input_pill";
import * as people from "./people";
import type {User} from "./people";
import type {NarrowTerm} from "./state_data";
import * as user_status from "./user_status";
import type {UserStatusEmojiInfo} from "./user_status";

export type SearchUserPill = {
    type: "search_user";
    operator: string;
    // TODO: It would be nice if we just call this `search_string` instead of
    // `display_value`, because we don't actually display this value for user
    // pills, but `display_value` is needed to hook into the generic input pill
    // logic and it would be a decent amount of work to change that.
    display_value: string;
    negated: boolean;
    users: {
        display_value: string;
        user_id: number;
        email: string;
        img_src: string;
        status_emoji_info: UserStatusEmojiInfo | undefined;
        should_add_guest_user_indicator: boolean;
        deactivated: boolean;
    }[];
};

type SearchPill =
    | {
          type: "search";
          display_value: string;
          description_html: string;
      }
    | SearchUserPill;

export type SearchPillWidget = InputPillContainer<SearchPill>;

export function create_item_from_search_string(search_string: string): SearchPill | undefined {
    const search_terms = Filter.parse(search_string);
    if (!search_terms.every((term) => Filter.is_valid_search_term(term))) {
        // This will cause pill validation to fail and trigger a shake animation.
        return undefined;
    }
    const description_html = Filter.search_description_as_html(search_terms);
    return {
        display_value: search_string,
        type: "search",
        description_html,
    };
}

export function get_search_string_from_item(item: SearchPill): string {
    return item.display_value;
}

export function create_pills($pill_container: JQuery): SearchPillWidget {
    const pills = input_pill.create({
        $container: $pill_container,
        create_item_from_text: create_item_from_search_string,
        get_text_from_item: get_search_string_from_item,
        split_text_on_comma: false,
        convert_to_pill_on_enter: false,
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
    const sign = negated ? "-" : "";
    const search_string = sign + operator + ":" + users.map((user) => user.email).join(",");
    const pill_data: SearchUserPill = {
        type: "search_user",
        operator,
        display_value: search_string,
        negated,
        users: users.map((user) => ({
            display_value: user.full_name,
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
        if (input.at(-1) === ":" && term.operand === "" && term === search_terms.at(-1)) {
            partial_pill = input;
            continue;
        }

        if (!Filter.is_valid_search_term(term)) {
            invalid_inputs.push(input);
            continue;
        }

        if (user_pill_operators.has(term.operator) && term.operand !== "") {
            const users = term.operand.split(",").map((email) => {
                // This is definitely not undefined, because we just validated it
                // with `Filter.is_valid_search_term`.
                const user = people.get_by_email(email)!;
                return user;
            });
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
    if (invalid_inputs.length) {
        $("#search_query").addClass("shake");
    }
}

export function get_current_search_string_for_widget(pill_widget: SearchPillWidget): string {
    const items = pill_widget.items();
    const search_strings = items.map((item) => item.display_value);
    return search_strings.join(" ");
}

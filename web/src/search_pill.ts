import $ from "jquery";
import assert from "minimalistic-assert";

import render_input_pill from "../templates/input_pill.hbs";
import render_search_list_item from "../templates/search_list_item.hbs";
import render_search_user_pill from "../templates/search_user_pill.hbs";

import {Filter} from "./filter.ts";
import {$t} from "./i18n.ts";
import * as input_pill from "./input_pill.ts";
import type {InputPill, InputPillContainer} from "./input_pill.ts";
import * as people from "./people.ts";
import type {User} from "./people.ts";
import {type Suggestion, search_term_description_html} from "./search_suggestion.ts";
import type {NarrowTerm} from "./state_data.ts";
import * as state_data from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as user_status from "./user_status.ts";
import type {UserStatusEmojiInfo} from "./user_status.ts";
import * as util from "./util.ts";

export type SearchUserPill = {
    type: "search_user";
    operator: NarrowTerm["operator"];
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
};

type SearchPill = ({type: "generic_operator"} & NarrowTerm) | SearchUserPill;

export type SearchPillWidget = InputPillContainer<SearchPill>;

// These operator types use user pills as operands.
const user_pill_operators = new Set(["dm", "dm-including", "sender"]);

export function create_item_from_search_string(search_string: string): SearchPill | undefined {
    const search_term = util.the(Filter.parse(search_string));
    if (!Filter.is_valid_search_term(search_term)) {
        // This will cause pill validation to fail and trigger a shake animation.
        return undefined;
    }
    return {
        type: "generic_operator",
        ...search_term,
    };
}

export function get_search_string_from_item(
    operator: string,
    operand: string,
    negated?: boolean,
): string {
    const sign = negated ? "-" : "";
    return `${sign}${operator}: ${operand}`;
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

// TODO: We're calculating `description_html` every time, even though
// we only show it (in `generate_pills_html`) for lines with only one
// pill. We can probably simplify things by separating out a function
// that generates `description_html` from the information in a single
// search pill, and remove `description_html` from the `Suggestion` type.
export function generate_pills_html(suggestion: Suggestion, text_query: string): string {
    const search_terms = Filter.parse(suggestion.search_string);

    let search_description_html: string;
    let capitalized_first_letter: string;
    const pill_render_data = search_terms.map((term, index) => {
        switch (term.operator) {
            case "dm":
            case "dm-including":
            case "sender":
                return search_user_pill_data_from_term(term);
            case "topic":
                if (term.operand === "") {
                    // There are three variants of this suggestion state:
                    //
                    // (1) This is an already formed pill, i.e. not in the text input
                    // (`text_query`), or is not the last term in the text input, and
                    //  therefore the empty operand represents "general chat".
                    //
                    // (2) The user has selected a topic operator, and and thus has
                    // exactly `topic:` or `-topic:` written out, and it's appropriate
                    // to suggest the "general chat" operand.
                    //
                    // (3) We're suggesting `topic` as a potential operator to add, say
                    // if the user has typed `-to` so far. For that case, we want to
                    // suggest adding a topic operator, but the user hasn't done anything
                    // that would suggest we should further complete "general chat" as an
                    // operand for that topic operator.
                    if (
                        // case 1
                        text_query === "" ||
                        index < search_terms.length - 1 ||
                        // case 2
                        text_query.trim().endsWith("topic:")
                    ) {
                        return {
                            type: "generic_operator",
                            ...term,
                            is_empty_string_topic: true,
                            sign: term.negated ? "-" : "",
                            topic_display_name: util.get_final_topic_display_name(""),
                        };
                    }
                    // case 3
                    return {
                        type: "generic_operator",
                        ...term,
                        is_empty_string_topic: true,
                        sign: term.negated ? "-" : "",
                    };
                }
                return {
                    type: "generic_operator",
                    ...term,
                    display_value: get_search_string_from_item(
                        term.operator,
                        util.get_final_topic_display_name(term.operand),
                        term.negated,
                    ),
                };

            case "channel":
                return {
                    type: "generic_operator",
                    ...term,
                    display_value: get_search_string_from_item(
                        term.operator,
                        term.operand ? stream_data.get_valid_sub_by_id_string(term.operand).name: term.operand,
                        term.negated,
                    ),
                };
            case "search":
                search_description_html = search_term_description_html(term);
                // We capitalize the beginning of the suggestion line if it's text (not
                // pills), which is only relevant for suggestions with search operators.
                if (index === 0) {
                    capitalized_first_letter = search_description_html.charAt(0).toUpperCase();
                    search_description_html = capitalized_first_letter + search_description_html.slice(1);
                }
                return {
                    type: "generic_operator",
                    ...term,
                    search_description_html,
                };
            default:
                return {
                    type: "generic_operator",
                    ...term,
                    display_value: get_search_string_from_item(
                        term.operator,
                        term.operand,
                        term.negated,
                    ),
                };
        }
    });

    // When there's a single pill on a suggestion line, we have space
    // to provide help text (description_html) explaining what the
    // operator does. When there's more than one pill we don't show it.
    if (pill_render_data.length === 1) {
        const render_data = util.the(pill_render_data);
        // Don't add description html for search terms, since those "pills"
        // are already set up to only display text and no pill. We also
        // don't show it for most user pills.
        if (render_data.type === "generic_operator" && render_data.operator !== "search") {
            return render_search_list_item({
                pills: pill_render_data,
                description_html: suggestion.description_html,
            });
        } else if (render_data.type === "search_user") {
            assert(render_data.operator === "sender" || render_data.operator === "dm" || render_data.operator === "dm-including");
            if (is_sent_by_me_pill(render_data)) {
                const description_html = render_data.negated
                    ? $t({defaultMessage: "Exclude messages you sent"})
                    : $t({defaultMessage: "Messages you sent"});
                return render_search_list_item({
                    pills: pill_render_data,
                    description_html,
                });
            }
        }
    }

    return render_search_list_item({
        pills: pill_render_data,
    });
}

export function create_pills($pill_container: JQuery): SearchPillWidget {
    const pills = input_pill.create({
        $container: $pill_container,
        create_item_from_text: create_item_from_search_string,
        get_text_from_item(item) {
            return get_search_string_from_item(
                item.operator,
                get_search_string_for_copying(item),
                item.negated,
            );
        },
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

function get_user_ids_from_term_with_user_pill_operator(term: NarrowTerm): number[] {
    if (term.operator === "sender") {
        return [term.operand];
    }

    assert(term.operator === "dm" || term.operator === "dm-including");
    return term.operand;
}

function search_user_pill_data_from_term(term: NarrowTerm): SearchUserPill {
    const user_ids = get_user_ids_from_term_with_user_pill_operator(term);
    const users = user_ids.map((user_id) => {
        const person = people.get_by_user_id(user_id);
        return person;
    });
    return search_user_pill_data(users, term.operator, term.negated ?? false);
}

function is_sent_by_me_pill(pill: SearchUserPill): boolean {
    return (
        pill.operator === "sender" &&
        pill.users.length === 1 &&
        util.the(pill.users).email === state_data.current_user.email
    );
}

function search_user_pill_data(
    users: User[],
    operator: NarrowTerm["operator"],
    negated: boolean,
): SearchUserPill {
    return {
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
}

function append_user_pill(
    users: User[],
    pill_widget: SearchPillWidget,
    operator: NarrowTerm["operator"],
    negated: boolean,
): void {
    const pill_data = search_user_pill_data(users, operator, negated);
    pill_widget.appendValidatedData(pill_data);
    pill_widget.clear_text();
}

export function set_search_bar_contents(
    search_terms: NarrowTerm[],
    pill_widget: SearchPillWidget,
    is_typeahead_visible: boolean,
    set_search_bar_text: (text: string) => void,
): void {
    pill_widget.clear(true);
    let partial_pill = "";
    const invalid_inputs = [];
    const search_operator_strings = [];
    const added_pills_as_input_strings = new Set(); // to prevent duplicating terms

    for (const term of search_terms) {
        const input = Filter.unparse([term]);
        if (added_pills_as_input_strings.has(input)) {
            return;
        }

        // If the last term looks something like `dm:`, we
        // don't want to make it a pill, since it isn't isn't
        // a complete search term yet.
        // Instead, we keep the partial pill to the end of the
        // search box as text input, which will update the
        // typeahead to show operand suggestions.
        // Note: We make a pill for `topic:` as it represents empty string topic
        // except the case where it suggests `topic` operator.
        if (
            input.at(-1) === ":" &&
            term.operand === "" &&
            term === search_terms.at(-1) &&
            (term.operator !== "topic" ||
                (is_typeahead_visible &&
                    $("#searchbox_form .typeahead-item.active .empty-topic-display").length === 0))
        ) {
            partial_pill = input;
            continue;
        }

        if (!Filter.is_valid_search_term(term)) {
            invalid_inputs.push(input);
            continue;
        }

        if (user_pill_operators.has(term.operator)) {
            const user_ids = get_user_ids_from_term_with_user_pill_operator(term);
            const users = user_ids.map((user_id) => {
                // This is definitely not undefined, because we just validated it
                // with `Filter.is_valid_search_term`.
                const user = people.get_by_user_id(user_id);
                return user;
            });
            append_user_pill(users, pill_widget, term.operator, term.negated ?? false);
            added_pills_as_input_strings.add(input);
        } else if (term.operator === "search") {
            // This isn't a pill, so we don't add it to `added_pills_as_input_strings`
            search_operator_strings.push(input);
        } else {
            pill_widget.appendValue(input);
            added_pills_as_input_strings.add(input);
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

function get_search_string_for_copying(item: SearchPill): string {
    // What we want user to copy to clipboard when they copy a search pill.
    switch (item.operator) {
        case "dm":
        case "dm-including":
        case "sender":
            assert(item.type === "search_user");
            return item.users.map((user) => user.email).join(",");
        case "topic":
            assert(item.type !== "search_user");
            return util.get_final_topic_display_name(item.operand);
        case "channel":
            assert(item.type !== "search_user");
            if (item.operand === "") {
                return "";
            }
            return stream_data.get_valid_sub_by_id_string(item.operand).name;
    
        default:
            assert(item.type !== "search_user");
            return item.operand;
    }
}

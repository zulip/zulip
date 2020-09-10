import $ from "jquery";
import _ from "lodash";

import {$t} from "./i18n";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as people from "./people";
import * as stream_data from "./stream_data";

function set_invalid_narrow_message(invalid_narrow_message) {
    const search_string_display = $("#empty_search_stop_words_string");
    search_string_display.text(invalid_narrow_message);
}

function show_search_query() {
    // when search bar contains multiple filters, only show search queries
    const current_filter = narrow_state.filter();
    const search_query = current_filter.operands("search")[0];
    const topic_query = current_filter.operands("topic-contains").join(" ");
    const content_query = current_filter.operands("content-contains").join(" ");
    const query_map = new Map();

    query_map.set("topic-contains", topic_query);
    query_map.set("content-contains", content_query);
    query_map.set("search", search_query);

    const search_string_display = $("#empty_search_stop_words_string");
    let query_contains_stop_words = false;

    function add_search_terms(query_words) {
        for (const query_word of query_words) {
            search_string_display.append(" ");

            // if query contains stop words, it is enclosed by a <del> tag
            if (page_params.stop_words.includes(query_word)) {
                // stop_words do not need sanitization so this is unnecessary but it is fail-safe.
                search_string_display.append($("<del>").text(query_word));
                query_contains_stop_words = true;
            } else {
                // We use .text("...") to sanitize the user-given query_string.
                search_string_display.append($("<span>").text(query_word));
            }
        }
    }

    // Also removes previous search_string if any
    search_string_display.text($t({defaultMessage: "You searched for:"}));

    // Add in stream:foo and topic:bar if present
    if (current_filter.has_operator("stream") || current_filter.has_operator("topic")) {
        let stream_topic_string = "";
        const stream = current_filter.operands("stream")[0];
        const topic = current_filter.operands("topic")[0];
        if (stream) {
            stream_topic_string = "stream: " + stream;
        }
        if (topic) {
            stream_topic_string = stream_topic_string + " topic: " + topic;
        }

        search_string_display.append(" ");
        search_string_display.append($("<span>").text(stream_topic_string));
    }

    for (const [search_type, query_words] of query_map.entries()) {
        if (query_words) {
            if (search_type !== "search") {
                search_string_display.append(" ");
                search_string_display.append(search_type + ":");
            }
            add_search_terms(query_words.split(" "));
        }
    }

    if (query_contains_stop_words) {
        const preamble = $t({defaultMessage: "Some common words were excluded from your search."});
        search_string_display.html(_.escape(preamble) + "<br/>" + search_string_display.html());
    }
}

function pick_empty_narrow_banner() {
    const default_banner = $("#empty_narrow_message");

    const current_filter = narrow_state.filter();

    if (current_filter === undefined) {
        return default_banner;
    }

    const first_term = current_filter.operators()[0];
    const first_operator = first_term.operator;
    const first_operand = first_term.operand;
    const num_operators = current_filter.operators().length;

    if (num_operators !== 1) {
        // For invalid-multi-operator narrows, we display an invalid narrow message
        const streams = current_filter.operands("stream");

        let invalid_narrow_message = "";
        // No message can have multiple streams
        if (streams.length > 1) {
            invalid_narrow_message = $t({
                defaultMessage:
                    "You are searching for messages that belong to more than one stream, which is not possible.",
            });
        }
        // No message can have multiple topics
        if (current_filter.operands("topic").length > 1) {
            invalid_narrow_message = $t({
                defaultMessage:
                    "You are searching for messages that belong to more than one topic, which is not possible.",
            });
        }
        // No message can have multiple senders
        if (current_filter.operands("sender").length > 1) {
            invalid_narrow_message = $t({
                defaultMessage:
                    "You are searching for messages that are sent by more than one person, which is not possible.",
            });
        }
        if (invalid_narrow_message !== "") {
            set_invalid_narrow_message(invalid_narrow_message);
            return $("#empty_search_narrow_message");
        }

        // For empty stream searches within other narrows, we display the stop words
        if (current_filter.operands("search").length > 0) {
            show_search_query();
            return $("#empty_search_narrow_message");
        }
        // For other multi-operator narrows, we just use the default banner
        return default_banner;
    }
    switch (first_operator) {
        case "is":
            switch (first_operand) {
                case "starred":
                    // You have no starred messages.
                    return $("#empty_star_narrow_message");
                case "mentioned":
                    return $("#empty_narrow_all_mentioned");
                case "private":
                    // You have no private messages.
                    return $("#empty_narrow_all_private_message");
                case "unread":
                    // You have no unread messages.
                    return $("#no_unread_narrow_message");
            }
            // fallthrough to default case if no match is found
            break;
        case "stream":
            if (!stream_data.is_subscribed(first_operand)) {
                // You are narrowed to a stream which does not exist or is a private stream
                // in which you were never subscribed.

                function can_toggle_narrowed_stream() {
                    const stream_name = narrow_state.stream();

                    if (!stream_name) {
                        return false;
                    }

                    const stream_sub = stream_data.get_sub(first_operand);
                    return stream_sub && stream_data.can_toggle_subscription(stream_sub);
                }

                if (can_toggle_narrowed_stream()) {
                    return $("#nonsubbed_stream_narrow_message");
                }

                return $("#nonsubbed_private_nonexistent_stream_narrow_message");
            }
            // else fallthrough to default case
            break;
        case "search":
        case "topic-contains":
        case "content-contains":
            // You are narrowed to empty search results.
            show_search_query();
            return $("#empty_search_narrow_message");
        case "pm-with":
            if (!people.is_valid_bulk_emails_for_compose(first_operand.split(","))) {
                if (!first_operand.includes(",")) {
                    return $("#non_existing_user");
                }
                return $("#non_existing_users");
            }
            if (!first_operand.includes(",")) {
                // You have no private messages with this person
                if (people.is_current_user(first_operand)) {
                    return $("#empty_narrow_self_private_message");
                }
                return $("#empty_narrow_private_message");
            }
            return $("#empty_narrow_multi_private_message");
        case "sender":
            if (people.get_by_email(first_operand)) {
                return $("#silent_user");
            }
            return $("#non_existing_user");
        case "group-pm-with":
            return $("#empty_narrow_group_private_message");
    }
    return default_banner;
}

export function show_empty_narrow_message() {
    $(".empty_feed_notice").hide();
    pick_empty_narrow_banner().show();
}

export function hide_empty_narrow_message() {
    $(".empty_feed_notice").hide();
}

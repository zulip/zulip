import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import * as compose_validate from "./compose_validate.ts";
import type {Filter} from "./filter.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import type {NarrowBannerData, SearchData} from "./narrow_error.ts";
import {narrow_error} from "./narrow_error.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as spectators from "./spectators.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as util from "./util.ts";

const SPECTATOR_STREAM_NARROW_BANNER = {
    title: "",
    html: $t_html(
        {
            defaultMessage: "This is not a <z-link>publicly accessible</z-link> conversation.",
        },
        {
            "z-link": (content_html) =>
                `<a target="_blank" rel="noopener noreferrer" href="/help/public-access-option">${content_html.join(
                    "",
                )}</a>`,
        },
    ),
};

const MENTIONS_VIEW_EMPTY_BANNER = {
    title: $t({defaultMessage: "This view will show messages where you are mentioned."}),
    html: $t_html(
        {
            defaultMessage:
                "To call attention to a message, you can mention a user, a group, topic participants, or all subscribers to a channel. Type @ in the compose box, and choose who you'd like to mention from the list of suggestions. <z-link>Learn more</z-link>",
        },
        {
            "z-link": (content_html) =>
                `<a target="_blank" rel="noopener noreferrer" href="/help/mention-a-user-or-group">${content_html.join(
                    "",
                )}</a>`,
        },
    ),
};

const STARRED_MESSAGES_VIEW_EMPTY_BANNER = {
    title: $t({defaultMessage: "You have no starred messages."}),
    html: $t_html(
        {
            defaultMessage:
                "Starring messages is a good way to keep track of important messages, such as tasks you need to go back to, or useful references. To star a message, hover over a message and click the <star-icon></star-icon>. <z-link>Learn more</z-link>",
        },
        {
            "star-icon": () => `<i class="zulip-icon zulip-icon-star" aria-hidden="true"></i>`,
            "z-link": (content_html) =>
                `<a target="_blank" rel="noopener noreferrer" href="/help/star-a-message">${content_html.join(
                    "",
                )}</a>`,
        },
    ),
};

const MUTED_TOPICS_IN_CHANNEL_EMPTY_BANNER = {
    title: $t({
        defaultMessage: "You have muted all the topics in this channel.",
    }),
    html: $t_html(
        {
            defaultMessage:
                "To view a muted topic, click <b>show all topics</b> in the left sidebar, and select one from the list. <z-link>Learn more</z-link>",
        },
        {
            "z-link": (content_html) =>
                `<a target="_blank" rel="noopener noreferrer" href="/help/mute-a-topic">${content_html.join("")}</a>`,
        },
    ),
};

const NO_SEARCH_RESULTS_TITLE = $t({defaultMessage: "No search results."});

function empty_search_query_banner(current_filter: Filter): NarrowBannerData {
    const search_query = current_filter.operands("search")[0];
    const query_words = search_query!.split(" ");

    const search_string_result: SearchData = {
        query_words: [],
        has_stop_word: false,
    };

    // Gather information about each query word
    for (const query_word of query_words) {
        if (realm.stop_words.includes(query_word)) {
            search_string_result.has_stop_word = true;
            search_string_result.query_words.push({
                query_word,
                is_stop_word: true,
            });
        } else {
            search_string_result.query_words.push({
                query_word,
                is_stop_word: false,
            });
        }
    }

    // We only show description of search query
    // when there are excluded stop words.
    if (search_string_result.has_stop_word) {
        return {
            title: NO_SEARCH_RESULTS_TITLE,
            search_data: search_string_result,
        };
    }
    return {title: NO_SEARCH_RESULTS_TITLE};
}

export function pick_empty_narrow_banner(current_filter: Filter): NarrowBannerData {
    const default_banner = {
        title: $t({defaultMessage: "There are no messages here."}),
        // Spectators cannot start a conversation.
        html: page_params.is_spectator
            ? ""
            : $t_html(
                  {
                      defaultMessage: "Why not <z-link>start the conversation</z-link>?",
                  },
                  {
                      "z-link": (content_html) =>
                          `<a href="#" class="empty_feed_compose_stream">${content_html.join(
                              "",
                          )}</a>`,
                  },
              ),
    };

    if (current_filter.is_in_home()) {
        // We're in the combined feed view.
        return {
            title: $t({defaultMessage: "There are no messages in your combined feed."}),
            html: page_params.is_spectator
                ? ""
                : $t_html(
                      {
                          defaultMessage:
                              "Would you like to <z-link>view messages in all public channels</z-link>?",
                      },
                      {
                          "z-link": (content_html) =>
                              `<a href="#narrow/channels/public">${content_html.join("")}</a>`,
                      },
                  ),
        };
    }

    const first_term = current_filter.terms()[0]!;
    const current_terms_types = current_filter.sorted_term_types();
    const first_operator = first_term.operator;
    const first_operand = first_term.operand;
    const num_terms = current_filter.terms().length;

    if (num_terms !== 1) {
        // For invalid-multi-operator narrows, we display an invalid narrow message
        const streams = current_filter.operands("channel");
        const topics = current_filter.operands("topic");

        // No message can have multiple streams
        if (streams.length > 1) {
            return {
                title: NO_SEARCH_RESULTS_TITLE,
                html: $t_html({
                    defaultMessage:
                        "<p>You are searching for messages that belong to more than one channel, which is not possible.</p>",
                }),
            };
        }
        // No message can have multiple topics
        if (topics.length > 1) {
            return {
                title: NO_SEARCH_RESULTS_TITLE,
                html: $t_html({
                    defaultMessage:
                        "<p>You are searching for messages that belong to more than one topic, which is not possible.</p>",
                }),
            };
        }
        // No message can have multiple senders
        if (current_filter.operands("sender").length > 1) {
            return {
                title: NO_SEARCH_RESULTS_TITLE,
                html: $t_html({
                    defaultMessage:
                        "<p>You are searching for messages that are sent by more than one person, which is not possible.</p>",
                }),
            };
        }

        // For empty search queries, we display excluded stop words
        if (current_filter.operands("search").length > 0) {
            return empty_search_query_banner(current_filter);
        }

        if (
            page_params.is_spectator &&
            first_operator === "channel" &&
            !stream_data.is_web_public_by_stream_id(Number.parseInt(first_operand, 10))
        ) {
            // For non web-public streams, show `login_to_access` modal.
            spectators.login_to_access(true);
            return SPECTATOR_STREAM_NARROW_BANNER;
        }

        if (streams.length === 1) {
            const stream_sub = stream_data.get_sub_by_id_string(
                util.the(current_filter.operands("channel")),
            );
            if (!stream_sub) {
                return {
                    title: $t({
                        defaultMessage:
                            "This channel doesn't exist, or you are not allowed to view it.",
                    }),
                };
            }
        }

        // A valid stream, but a topic that doesn't exist yet.
        if (num_terms === 2 && streams.length === 1 && topics.length === 1) {
            return default_banner;
        }

        if (
            _.isEqual(current_terms_types, ["sender", "has-reaction"]) &&
            current_filter.operands("sender")[0] === people.my_current_email()
        ) {
            return {
                title: $t({defaultMessage: "None of your messages have emoji reactions yet."}),
                html: $t_html(
                    {
                        defaultMessage: "Learn more about emoji reactions <z-link>here</z-link>.",
                    },
                    {
                        "z-link": (content_html) =>
                            `<a target="_blank" rel="noopener noreferrer" href="/help/emoji-reactions">${content_html.join(
                                "",
                            )}</a>`,
                    },
                ),
            };
        }

        // For other multi-operator narrows, we just use the default banner
        return {
            title: NO_SEARCH_RESULTS_TITLE,
        };
    }

    switch (first_operator) {
        case "is":
            switch (first_operand) {
                case "starred":
                    return STARRED_MESSAGES_VIEW_EMPTY_BANNER;
                case "mentioned":
                    return MENTIONS_VIEW_EMPTY_BANNER;
                case "dm":
                    // You have no direct messages.
                    return {
                        title: $t({defaultMessage: "You have no direct messages yet!"}),
                        html: $t_html(
                            {
                                defaultMessage: "Why not <z-link>start the conversation</z-link>?",
                            },
                            {
                                // TODO: The href here is a bit weird; we probably want to migrate
                                // this to a button element down the line.
                                "z-link": (content_html) =>
                                    `<a href="#" class="empty_feed_compose_private">${content_html.join(
                                        "",
                                    )}</a>`,
                            },
                        ),
                    };
                case "unread":
                    // You have no unread messages.
                    return {
                        title: $t({defaultMessage: "You have no unread messages!"}),
                    };
                case "resolved":
                    return {
                        title: $t({defaultMessage: "No topics are marked as resolved."}),
                    };
                case "followed":
                    return {
                        title: $t({defaultMessage: "You aren't following any topics."}),
                    };

                case "muted":
                    return {
                        title: $t({
                            defaultMessage: "You have no messages in muted topics and channels.",
                        }),
                    };
            }
            // fallthrough to default case if no match is found
            break;
        case "channel": {
            const stream_sub = stream_data.get_sub_by_id_string(first_operand);
            if (!stream_sub?.subscribed) {
                // You are narrowed to a channel that either does not exist,
                // is private, or a channel you're not currently subscribed to.
                if (page_params.is_spectator) {
                    spectators.login_to_access(true);
                    return SPECTATOR_STREAM_NARROW_BANNER;
                }
                if (stream_sub && stream_data.can_toggle_subscription(stream_sub)) {
                    return default_banner;
                }
                return {
                    title: $t({
                        defaultMessage:
                            "This channel doesn't exist, or you are not allowed to view it.",
                    }),
                };
            }
            assert(message_lists.current !== undefined);
            if (message_lists.current.visibly_empty() && !message_lists.current.empty()) {
                // The current message list appears empty, but there are
                // messages in muted topics.
                return MUTED_TOPICS_IN_CHANNEL_EMPTY_BANNER;
            }
            // else fallthrough to default case
            break;
        }
        case "search": {
            // You are narrowed to empty search results.
            return empty_search_query_banner(current_filter);
        }
        case "dm": {
            if (!people.is_valid_bulk_emails_for_compose(first_operand.split(","))) {
                if (!first_operand.includes(",")) {
                    return {
                        title: $t({defaultMessage: "This user does not exist!"}),
                    };
                }
                return {
                    title: $t({defaultMessage: "One or more of these users do not exist!"}),
                };
            }
            const user_ids = people.emails_strings_to_user_ids_array(first_operand);
            assert(user_ids?.[0] !== undefined);
            const user_ids_string = util.sorted_ids(user_ids).join(",");
            const direct_message_error_string =
                compose_validate.check_dm_permissions_and_get_error_string(user_ids_string);
            if (direct_message_error_string) {
                return {
                    title: direct_message_error_string,
                    html: $t_html(
                        {
                            defaultMessage: "<z-link>Learn more.</z-link>",
                        },
                        {
                            "z-link": (content_html) =>
                                `<a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">${content_html.join("")}</a>`,
                        },
                    ),
                };
            }
            if (!first_operand.includes(",")) {
                const recipient_user = people.get_by_user_id(user_ids[0]);
                // You have no direct messages with this person
                if (people.is_my_user_id(recipient_user.user_id)) {
                    return {
                        title: $t({
                            defaultMessage:
                                "You have not sent any direct messages to yourself yet!",
                        }),
                        html: $t_html({
                            defaultMessage:
                                "Use this space for personal notes, or to test out Zulip features.",
                        }),
                    };
                }
                // If the recipient is deactivated, we cannot start the conversation.
                if (!people.is_person_active(recipient_user.user_id)) {
                    return {
                        title: $t(
                            {
                                defaultMessage: "You have no direct messages with {person}.",
                            },
                            {person: recipient_user.full_name},
                        ),
                    };
                }
                return {
                    title: $t(
                        {
                            defaultMessage: "You have no direct messages with {person} yet.",
                        },
                        {person: recipient_user.full_name},
                    ),
                    html: $t_html(
                        {
                            defaultMessage: "Why not <z-link>start the conversation</z-link>?",
                        },
                        {
                            "z-link": (content_html) =>
                                `<a href="#" class="empty_feed_compose_private">${content_html.join(
                                    "",
                                )}</a>`,
                        },
                    ),
                };
            }
            if (people.get_non_active_user_ids_count(user_ids) !== 0) {
                return {
                    title: $t({defaultMessage: "You have no direct messages with these users."}),
                };
            }
            return {
                title: $t({defaultMessage: "You have no direct messages with these users yet."}),
                html: $t_html(
                    {
                        defaultMessage: "Why not <z-link>start the conversation</z-link>?",
                    },
                    {
                        "z-link": (content_html) =>
                            `<a href="#" class="empty_feed_compose_private">${content_html.join(
                                "",
                            )}</a>`,
                    },
                ),
            };
        }
        case "sender": {
            const sender = people.get_by_email(first_operand);
            if (sender) {
                return {
                    title: $t(
                        {
                            defaultMessage:
                                "You haven't received any messages sent by {person} yet.",
                        },
                        {person: sender.full_name},
                    ),
                };
            }
            return {
                title: $t({defaultMessage: "This user does not exist!"}),
            };
        }
        case "dm-including": {
            const person_in_dms = people.get_by_email(first_operand);
            if (!person_in_dms) {
                return {
                    title: $t({defaultMessage: "This user does not exist!"}),
                };
            }
            const person_id_string = person_in_dms.user_id.toString();
            const direct_message_error_string =
                compose_validate.check_dm_permissions_and_get_error_string(person_id_string);
            if (direct_message_error_string) {
                return {
                    title: direct_message_error_string,
                    html: $t_html(
                        {
                            defaultMessage: "<z-link>Learn more.</z-link>",
                        },
                        {
                            "z-link": (content_html) =>
                                `<a target="_blank" rel="noopener noreferrer" href="/help/restrict-direct-messages">${content_html.join("")}</a>`,
                        },
                    ),
                };
            }
            if (people.is_my_user_id(person_in_dms.user_id)) {
                return {
                    title: $t({
                        defaultMessage: "You don't have any direct message conversations yet.",
                    }),
                };
            }
            return {
                title: $t(
                    {
                        defaultMessage: "You have no direct messages including {person} yet.",
                    },
                    {person: person_in_dms.full_name},
                ),
            };
        }
    }
    return default_banner;
}

export function show_empty_narrow_message(current_filter: Filter): void {
    $(".empty_feed_notice_main").empty();
    const rendered_narrow_banner = narrow_error(pick_empty_narrow_banner(current_filter));
    $(".empty_feed_notice_main").html(rendered_narrow_banner);
}

export function hide_empty_narrow_message(): void {
    $(".empty_feed_notice_main").empty();
}

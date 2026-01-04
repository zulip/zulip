import render_status_emoji from "../templates/status_emoji.hbs";
import render_user_full_name from "../templates/user_full_name.hbs";

import type {BuddyUserInfo} from "./buddy_data.ts";
import * as hbs from "./hbs_bridge.ts";
import * as h from "./html.ts";

// FIX THIS!!! (we can import it)
function $t(info: {defaultMessage: string}): string {
    return info.defaultMessage;
}

// This builds the UI that looks like "<triangle icon> OTHERS" in the buddy list.
// Users can collapse or un-collapse the users by clicking on the header.
// The **entire** section header is a click target.  Most of the smaller components
// only get drawn and styled.
export function buddy_list_section_header(info: {
    id: string;
    header_text: string;
    is_collapsed: boolean;
}): h.Block {
    // This only draws the icon.
    // All the click handlers act on the div tag
    // that gets wrapped around it.
    function section_rotation_icon(): h.Tag {
        // The rotation_class sets an eventual class for the icon as either
        // "rotate-icon-right" or "rotate-icon-down".
        // They lead to rotate: 0deg and rotate: 90deg in the Zulip CSS.
        function rotation_class(): h.TrustedIfElseString {
            return h.trusted_if_else_string({
                bool: h.bool_var({label: "is_collapsed", b: info.is_collapsed}),
                yes_val: h.trusted_simple_string("rotate-icon-right"),
                no_val: h.trusted_simple_string("rotate-icon-down"),
            });
        }

        return h.i_tag({
            classes: [
                "buddy-list-section-toggle",
                "zulip-icon",
                "zulip-icon-heading-triangle-right",
                rotation_class(),
            ],
            attrs: [h.attr("aria-hidden", h.trusted_simple_string("true"))],
        });
    }

    // The heading_text_span creates a span with the text of either
    // "THIS CONVERSATION" or "OTHERS" as determined by the color.
    // It has no handlers attached directly to it.
    // The buddy-list-heading-text class controls overflow, alignment,
    // and wrapping. Most of the additional styling (fonts, color, etc.)
    // happens via styles on the surrounding element(s).
    function heading_text_span(): h.Tag {
        return h.span_tag({
            source_format: "inline",
            classes: ["buddy-list-heading-text"],
            children: [
                h.text_var({
                    label: "header_text",
                    s: h.unescaped_text_string(info.header_text),
                }),
            ],
        });
    }

    // user_count_span builds an outer span around a text element that
    // says something like "(35K)" to indicate how many users are inside
    // our section of the buddy list.
    function user_count_span(): h.Tag {
        return h.span_tag({
            source_format: "block",
            classes: [
                // The buddy-list-heading-user-count-with-parens class is used to
                // drive styling in the Zulip CSS. It only sets opacity as of
                // this writing.
                "buddy-list-heading-user-count-with-parens",
                "hide",
            ],
            children: [
                h.parenthesized_tag(
                    // inner span for count of people in the section
                    h.span_tag({
                        classes: ["buddy-list-heading-user-count"],
                    }),
                ),
            ],
        });
    }

    // The h5 tag encloses the heading text (e.g. "OTHERS") and the user count
    // (e.g. "(35K)") but not the rotation icon (for reasons not clear, but probably fine).
    function buddy_list_heading(): h.Tag {
        return h.h5_tag({
            force_attrs_before_class: true,
            classes: [
                // The buddy-list-heading drives a lot of CSS styling. It's also used by jQuery
                // to find the element to attach to for mouse handling.
                "buddy-list-heading",
                // The no-style class turns off text decoration and sets the cursor
                // to a pointer, since this is gonna be part of the overall click
                // target to toggle whether you show uses in the section.
                "no-style",
                // The hidden-for-spectators class hides the section from Zulip
                // spectators using the standard mechanisms.
                "hidden-for-spectators",
            ],
            attrs: [
                h.attr(
                    "id",
                    h.trusted_attr_string_var({
                        label: "id",
                        s: h.unescaped_attr_string(info.id),
                    }),
                ),
            ],
            children: [
                heading_text_span(),
                h.comment("Hide the count until we have fetched data to display the correct count"),
                user_count_span(),
            ],
        });
    }

    return h.block({elements: [section_rotation_icon(), buddy_list_heading()]});
}

export function view_all_subscribers(info: {stream_edit_hash: string}): h.Block {
    function view_all_subscribers_span(): h.Tag {
        return h.span_tag({
            source_format: "block",
            classes: ["right-sidebar-wrappable-text-inner"],
            children: [
                h.translated_text({
                    translated_text: $t({
                        defaultMessage: "View all subscribers",
                    }),
                }),
            ],
        });
    }

    function href_to_view_all_subscribers_in_the_stream_edit_ui(): h.TrustedAttrStringVar {
        return h.trusted_attr_string_var({
            label: "stream_edit_hash",
            s: h.unescaped_attr_string(info.stream_edit_hash),
        });
    }

    function right_sidebar_wrappable_text_container(): h.Tag {
        return h.a_tag({
            source_format: "block",
            classes: ["right-sidebar-wrappable-text-container"],
            attrs: [h.attr("href", href_to_view_all_subscribers_in_the_stream_edit_ui())],
            children: [view_all_subscribers_span()],
        });
    }
    return h.block({elements: [right_sidebar_wrappable_text_container()]});
}

export function view_all_users(): h.Block {
    function view_all_users_span(): h.Tag {
        return h.span_tag({
            source_format: "block",
            classes: ["right-sidebar-wrappable-text-inner"],
            children: [
                h.translated_text({
                    translated_text: $t({
                        defaultMessage: "View all users",
                    }),
                }),
            ],
        });
    }

    function right_sidebar_wrappable_text_container(): h.Tag {
        return h.a_tag({
            source_format: "block",
            classes: ["right-sidebar-wrappable-text-container"],
            attrs: [h.attr("href", h.trusted_simple_string("#organization/users"))],
            children: [view_all_users_span()],
        });
    }

    return h.block({elements: [right_sidebar_wrappable_text_container()]});
}

export function empty_list_widget_for_list(info: {empty_list_message: string}): h.Block {
    function li_tag(): h.Tag {
        return h.li_tag({
            source_format: "inline",
            classes: ["empty-list-message"],
            children: [
                h.text_var({
                    label: "empty_list_message",
                    s: h.unescaped_text_string(info.empty_list_message),
                }),
            ],
        });
    }

    return h.block({elements: [li_tag()]});
}

export function poll_widget(): h.Block {
    // The add_question_widget is responsible for taking the question input
    // from the user.
    function add_question_widget(): h.InputTextTag {
        return h.input_text_tag({
            placeholder_value: h.translated_attr_value({
                translated_string: $t({defaultMessage: "Add question"}),
            }),
            // The poll-question class is mainly used for styling the input.
            classes: ["poll-question"],
        });
    }

    // poll_question_header displays the heading text for the poll.
    function poll_question_header(): h.Tag {
        return h.h4_tag({
            // The poll-question-header class is present on this h4 when
            // the header is not in input_mode.
            classes: ["poll-question-header"],
        });
    }

    // This lets you input some alternate heading text for the question
    // when in edit mode.
    function poll_question_bar(): h.Tag {
        return h.div_tag({
            // poll-question-bar is associated with styling the input container as a flexbox.
            classes: ["poll-question-bar"],
            children: [add_question_widget(), remove_icon(), poll_question_check_icon()],
        });
    }

    // Clicking on the edit_question_icon toggles the header text h4
    // to become an input which lets you edit the heading text for the poll.
    function edit_question_icon(): h.Tag {
        return h.i_tag({
            classes: [
                "fa",
                "fa-pencil",
                // The event listener for changing to input mode is attached
                // to the poll-edit-question class, it also has some styling associated
                // with it.
                "poll-edit-question",
            ],
        });
    }

    // Clicking on the remove_icon lets you abort the edit question mode
    // and switch back to the showing the previous question heading text.
    function remove_icon(): h.Tag {
        return h.icon_button({
            icon_classes: ["fa", "fa-remove"],
            // poll-question-remove has the click listener attached to it.
            button_classes: ["poll-question-remove"],
        });
    }

    // Clicking on the poll_question_check_icon lets you update the heading text
    // to the one you entered in poll_question_bar
    function poll_question_check_icon(): h.Tag {
        return h.icon_button({
            icon_classes: ["fa", "fa-check"],
            // poll-question-check has the click listener attached to it to submit the question
            // heading text.
            button_classes: ["poll-question-check"],
        });
    }

    // This is the input field for adding new options to the poll.
    function new_option_input(): h.InputTextTag {
        return h.input_text_tag({
            placeholder_value: h.translated_attr_value({
                translated_string: $t({defaultMessage: "New option"}),
            }),
            // poll-option is used for styling (font weight, flexbox properties,
            // color, padding, alignment, etc.) using Zulip CSS.
            classes: ["poll-option"],
        });
    }

    // This is displayed when you are looking at a poll which has no
    // questions heading text yet and is not created by you.
    function please_wait_for_the_question(): h.Tag {
        return h.div_tag({
            source_format: "block",
            // poll-please-wait is just a plain wrapper for the waiting text.
            classes: ["poll-please-wait"],
            children: [
                h.translated_text({
                    translated_text: $t({
                        defaultMessage:
                            "We are about to have a poll.  Please wait for the question.",
                    }),
                    force_single_quotes: true,
                }),
            ],
        });
    }

    // This wraps the question header text, question header input and the edit question icon.
    function poll_widget_header_area(): h.Tag {
        return h.div_tag({
            classes: ["poll-widget-header-area"],
            children: [poll_question_header(), edit_question_icon(), poll_question_bar()],
        });
    }

    // This lets you add a new option to the poll.
    function add_option_button(): h.Tag {
        return h.button_tag({
            source_format: "inline",
            // poll-option is used for styling (font weight, flexbox properties,
            // color, padding, alignment, etc.) using Zulip CSS.
            classes: ["poll-option"],
            children: [
                h.translated_text({
                    translated_text: $t({
                        defaultMessage: "Add option",
                    }),
                }),
            ],
        });
    }

    // This wraps the option input and the "Add option" button.
    function poll_option_bar(): h.Tag {
        return h.div_tag({
            // poll-option-bar contains some flexbox styling in Zulip CSS.
            classes: ["poll-option-bar"],
            children: [new_option_input(), add_option_button()],
        });
    }

    // This is the list that wraps the poll options.
    function ul_for_poll_options(): h.Tag {
        return h.ul_tag({
            source_format: "block",
            classes: ["poll-widget"],
            pink: true,
        });
    }

    // Main widget containing the poll widget.
    function widget(): h.Tag {
        return h.div_tag({
            classes: ["poll-widget"],
            children: [
                poll_widget_header_area(),
                please_wait_for_the_question(),
                ul_for_poll_options(),
                poll_option_bar(),
            ],
        });
    }

    return h.block({elements: [widget()]});
}

export function presence_row(info: BuddyUserInfo): h.Block {
    // Responsible for showing the circle which displays the user's current status.
    function user_circle_span(): h.Tag {
        return h.span_tag({
            classes: [
                "zulip-icon",
                h.trusted_class_with_var_suffix({
                    prefix: "zulip-icon",
                    var_suffix: h.trusted_attr_string_var({
                        label: "user_circle_class",
                        s: h.unescaped_attr_string(info.user_circle_class),
                    }),
                }),
                h.trusted_attr_string_var({
                    label: "user_circle_class",
                    s: h.unescaped_attr_string(info.user_circle_class),
                }),
                "user-circle",
            ],
        });
    }

    function status_text(): h.Tag {
        return h.span_tag({
            source_format: "inline",
            classes: ["status-text"],
            children: [
                h.text_var({
                    label: "status_text",
                    s: h.unescaped_attr_string(info.status_text ?? ""),
                }),
            ],
        });
    }

    function user_name_and_status_emoji(): h.Tag {
        return h.div_tag({
            classes: ["user-name-and-status-emoji"],
            children: [
                h.partial({
                    inner_label: "user_full_name",
                    trusted_html: h.trusted_html(render_user_full_name(info)),
                }),
                h.partial({
                    inner_label: "status_emoji",
                    trusted_html: h.trusted_html(render_status_emoji(info.status_emoji_info)),
                    custom_context: "status_emoji_info",
                }),
            ],
        });
    }
    function user_presence_link(is_compact: boolean): h.Tag {
        const user_presence_link_children = [user_name_and_status_emoji()];
        if (!is_compact) {
            user_presence_link_children.push(status_text());
        }
        return h.a_tag({
            source_format: "block",
            classes: ["user-presence-link"],
            attrs: [
                h.attr(
                    "href",
                    h.trusted_attr_string_var({
                        label: "href",
                        s: h.unescaped_attr_string(info.href),
                    }),
                ),
                h.attr("draggable", h.trusted_simple_string("false")),
            ],
            children: user_presence_link_children,
        });
    }

    // Returns the user profile picture with the circle for current status
    function user_profile_picture(): h.Tag {
        return h.div_tag({
            source_format: "block",
            classes: ["user-profile-picture-container"],
            children: [
                h.div_tag({
                    classes: ["user-profile-picture", "avatar-preload-background"],
                    children: [
                        h.img_tag({
                            attrs: [
                                h.attr("loading", h.trusted_simple_string("lazy")),
                                h.attr(
                                    "src",
                                    h.trusted_attr_string_var({
                                        label: "profile_picture",
                                        s: h.unescaped_attr_string(info.profile_picture),
                                    }),
                                ),
                            ],
                        }),
                        user_circle_span(),
                    ],
                }),
            ],
        });
    }

    // When the user setting for buddy list is set to "Show Status Text",
    // we render the block returned by `status_profile`
    function status_profile(): h.Block {
        return h.block({elements: [user_circle_span(), user_presence_link(false)]});
    }

    // When the user list style setting for buddy list is set to "Show Avatar",
    // we render the block returned by `avatar_profile`
    function avatar_profile(): h.Block {
        return h.block({elements: [user_profile_picture(), user_presence_link(false)]});
    }

    // When the user list style setting for buddy list is set to "Compact",
    // we render the block returned by `avatar_profile`
    function compact_profile(): h.Block {
        return h.block({elements: [user_circle_span(), user_presence_link(true)]});
    }

    // Used to render a three-dot-menu icon for lists that don't contain
    // user avatar.
    function user_list_sidebar_menu_icon(): h.Tag {
        return h.span_tag({
            source_format: "inline",
            classes: ["sidebar-menu-icon", "user-list-sidebar-menu-icon"],
            children: [
                h.i_tag({
                    classes: ["zulip-icon", "zulip-icon-more-vertical"],
                    attrs: [h.attr("aria-hidden", h.trusted_simple_string("true"))],
                }),
            ],
        });
    }

    function presence_row_list_item(): h.Tag {
        return h.li_tag({
            force_attrs_before_class: true,
            attrs: [
                h.attr(
                    "data-user-id",
                    h.trusted_attr_string_var({
                        label: "user_id",
                        s: h.unescaped_attr_string(info.user_id.toString()),
                    }),
                ),
                h.attr(
                    "data-name",
                    h.trusted_attr_string_var({
                        label: "name",
                        s: h.unescaped_attr_string(info.name),
                    }),
                ),
            ],
            classes: [
                "user_sidebar_entry",
                h.trusted_if_string({
                    bool: h.bool_var({
                        label: "user_list_style.WITH_AVATAR",
                        b: info.user_list_style.WITH_AVATAR,
                    }),
                    val: h.trusted_simple_string("with_avatar"),
                }),

                h.trusted_if_string({
                    bool: h.bool_var({
                        label: "has_status_text",
                        b: info.has_status_text,
                    }),
                    val: h.trusted_simple_string("with_status"),
                }),

                h.trusted_if_string({
                    bool: h.bool_var({
                        label: "is_current_user",
                        b: info.is_current_user,
                    }),
                    val: h.trusted_simple_string("user_sidebar_entry_me "),
                }),
                h.trusted_simple_string("narrow-filter"),
                h.trusted_if_string({
                    bool: h.bool_var({
                        label: "faded",
                        b: info.faded ?? false,
                    }),
                    val: h.trusted_simple_string(" user-fade "),
                }),
            ],
            children: [
                h.div_tag({
                    classes: ["selectable_sidebar_block"],
                    children: [
                        hbs.if_bool_then_x_else_if_bool_then_y_else_z({
                            if_info: {
                                bool: h.bool_var({
                                    label: "user_list_style.WITH_STATUS",
                                    b: info.user_list_style.WITH_STATUS,
                                }),
                                block: status_profile(),
                            },
                            else_if_info: {
                                bool: h.bool_var({
                                    label: "user_list_style.WITH_AVATAR",
                                    b: info.user_list_style.WITH_AVATAR,
                                }),
                                block: avatar_profile(),
                            },
                            else_block: compact_profile(),
                        }),
                        h.span_tag({
                            source_format: "inline",
                            classes: [
                                "unread_count",
                                h.trusted_unless_string({
                                    bool: h.bool_var({
                                        label: "num_unread",
                                        b: Boolean(info.num_unread),
                                    }),
                                    val: h.trusted_simple_string("hide"),
                                }),
                            ],
                            children: [
                                hbs.if_bool_then_block({
                                    bool: h.bool_var({
                                        label: "num_unread",
                                        b: Boolean(info.num_unread),
                                    }),
                                    block: h.block({
                                        elements: [
                                            h.text_var({
                                                label: "num_unread",
                                                s: h.unescaped_text_string(
                                                    info.num_unread.toString(),
                                                ),
                                            }),
                                        ],
                                    }),
                                }),
                            ],
                        }),
                    ],
                }),
                hbs.unless_bool_then_block({
                    source_format: "strange_block",
                    bool: h.bool_var({
                        label: "user_list_style.WITH_AVATAR",
                        b: info.user_list_style.WITH_AVATAR,
                    }),
                    block: h.block({elements: [user_list_sidebar_menu_icon()]}),
                }),
            ],
        });
    }
    return h.block({elements: [presence_row_list_item()]});
}

export function presence_rows(info: {presence_rows: BuddyUserInfo[]}): h.SimpleEach {
    return h.simple_each({
        each_label: "presence_rows",
        loop_var_partial_label: "presence_row",
        get_blocks(): h.Block[] {
            return info.presence_rows.map((buddy_info) => presence_row(buddy_info));
        },
    });
}

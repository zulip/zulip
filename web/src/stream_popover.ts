import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import * as z from "zod/mini";

import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";
import render_inline_stream_or_topic_reference from "../templates/inline_stream_or_topic_reference.hbs";
import render_topic_already_exists_warning_banner from "../templates/modal_banner/topic_already_exists_warning_banner.hbs";
import render_unsubscribed_participants_warning_banner from "../templates/modal_banner/unsubscribed_participants_warning_banner.hbs";
import render_move_topic_to_stream from "../templates/move_topic_to_stream.hbs";
import render_left_sidebar_stream_actions_popover from "../templates/popovers/left_sidebar/left_sidebar_stream_actions_popover.hbs";

import * as blueslip from "./blueslip.ts";
import type {Typeahead} from "./bootstrap_typeahead.ts";
import * as browser_history from "./browser_history.ts";
import * as clipboard_handler from "./clipboard_handler.ts";
import * as compose_banner from "./compose_banner.ts";
import * as composebox_typeahead from "./composebox_typeahead.ts";
import {ConversationParticipants} from "./conversation_participants.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_edit from "./message_edit.ts";
import * as message_lists from "./message_lists.ts";
import type {Message} from "./message_store.ts";
import * as message_util from "./message_util.ts";
import * as message_view from "./message_view.ts";
import * as narrow_state from "./narrow_state.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import {left_sidebar_tippy_options} from "./popover_menus.ts";
import {web_channel_default_view_values} from "./settings_config.ts";
import {realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as stream_settings_components from "./stream_settings_components.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as sub_store from "./sub_store.ts";
import * as subscriber_api from "./subscriber_api.ts";
import * as ui_report from "./ui_report.ts";
import * as ui_util from "./ui_util.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

// In this module, we manage stream popovers
// that pop up from the left sidebar.
let stream_widget_value: number | undefined;
let move_topic_to_stream_topic_typeahead: Typeahead<string> | undefined;
const last_propagate_mode_for_conversation = new Map<string, string>();

export function stream_sidebar_menu_handle_keyboard(key: string): void {
    if (popover_menus.is_color_picker_popover_displayed()) {
        const $color_picker_popover_instance = popover_menus.get_color_picker_popover();
        if (!$color_picker_popover_instance) {
            return;
        }
        popover_menus.sidebar_menu_instance_handle_keyboard($color_picker_popover_instance, key);
        return;
    }
    const $stream_actions_popover_instance = popover_menus.get_stream_actions_popover();
    if (!$stream_actions_popover_instance) {
        return;
    }
    popover_menus.sidebar_menu_instance_handle_keyboard($stream_actions_popover_instance, key);
}

export function elem_to_stream_id($elem: JQuery): number {
    const stream_id = Number.parseInt($elem.attr("data-stream-id")!, 10);

    if (stream_id === undefined) {
        blueslip.error("could not find stream id");
    }

    return stream_id;
}

export function hide_stream_popover(instance: tippy.Instance): void {
    ui_util.hide_left_sidebar_menu_icon();
    instance.destroy();
    popover_menus.popover_instances.stream_actions_popover = null;
}

function stream_popover_sub(
    e: JQuery.ClickEvent<tippy.PopperElement, undefined>,
): sub_store.StreamSubscription {
    const $elem = $(e.currentTarget).parents("ul");
    const stream_id = elem_to_stream_id($elem);
    const sub = sub_store.get(stream_id);
    if (!sub) {
        throw new Error(`Unknown stream ${stream_id}`);
    }
    return sub;
}

function build_stream_popover(opts: {elt: HTMLElement; stream_id: number}): void {
    const {elt, stream_id} = opts;

    // This will allow the user to close the popover by clicking
    // on the reference element if the popover is already open.
    if (popover_menus.get_stream_actions_popover()?.reference === elt) {
        return;
    }

    const is_triggered_from_inbox = elt.classList.contains("inbox-stream-menu");
    const stream_hash = hash_util.channel_url_by_user_setting(stream_id);
    const show_go_to_channel_feed =
        (is_triggered_from_inbox ||
            user_settings.web_channel_default_view !==
                web_channel_default_view_values.channel_feed.code) &&
        !stream_data.is_empty_topic_only_channel(stream_id);
    const show_go_to_list_of_topics =
        (is_triggered_from_inbox ||
            user_settings.web_channel_default_view !==
                web_channel_default_view_values.list_of_topics.code) &&
        !stream_data.is_empty_topic_only_channel(stream_id);
    const stream_unread = unread.unread_count_info_for_stream(stream_id);
    const stream_unread_count = stream_unread.unmuted_count + stream_unread.muted_count;
    const has_unread_messages = stream_unread_count > 0;
    const content = render_left_sidebar_stream_actions_popover({
        stream: {
            ...sub_store.get(stream_id),
            url: browser_history.get_full_url(stream_hash),
            list_of_topics_view_url: hash_util.by_channel_topic_list_url(stream_id),
        },
        has_unread_messages,
        show_go_to_channel_feed,
        show_go_to_list_of_topics,
    });

    popover_menus.toggle_popover_menu(elt, {
        // Add a delay to separate `hideOnClick` and `onShow` so that
        // `onShow` is called after `hideOnClick`.
        // See https://github.com/atomiks/tippyjs/issues/230 for more details.
        delay: [100, 0],
        ...left_sidebar_tippy_options,
        onCreate(instance) {
            const $popover = $(instance.popper);
            $popover.addClass("stream-popover-root");
            instance.setContent(ui_util.parse_html(content));
        },
        onMount(instance) {
            const $popper = $(instance.popper);
            popover_menus.popover_instances.stream_actions_popover = instance;
            ui_util.show_left_sidebar_menu_icon(elt);

            // Go to channel feed instead of first topic.
            $popper.on("click", ".stream-popover-go-to-channel-feed", (e) => {
                e.preventDefault();
                e.stopPropagation();
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);
                message_view.show(
                    [
                        {
                            operator: "stream",
                            operand: sub.stream_id.toString(),
                        },
                    ],
                    {trigger: "stream-popover"},
                );
            });

            $popper.on("click", ".stream-popover-go-to-list-of-topics", (e) => {
                e.stopPropagation();
                hide_stream_popover(instance);
            });

            // Stream settings
            $popper.on("click", ".open_stream_settings", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);

                // Admin can change any stream's name & description either stream is public or
                // private, subscribed or unsubscribed.
                const can_change_stream_permissions =
                    stream_data.can_change_permissions_requiring_metadata_access(sub);
                let stream_edit_hash = hash_util.channels_settings_edit_url(sub, "general");
                if (!can_change_stream_permissions) {
                    stream_edit_hash = hash_util.channels_settings_edit_url(sub, "personal");
                }
                browser_history.go_to_location(stream_edit_hash);
            });

            // Pin/unpin
            $popper.on("click", ".pin_to_top", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);
                stream_settings_ui.toggle_pin_to_top_stream(sub);
                e.stopPropagation();
            });

            // Mark all messages in stream as read
            $popper.on("click", ".mark_stream_as_read", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);
                unread_ops.mark_stream_as_read(sub.stream_id);
                e.stopPropagation();
            });

            // Mark all messages in stream as unread
            $popper.on("click", ".mark_stream_as_unread", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);
                unread_ops.mark_stream_as_unread(sub.stream_id);
                e.stopPropagation();
            });

            // Mute/unmute
            $popper.on("click", ".toggle_stream_muted", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);
                stream_settings_api.set_stream_property(sub, {
                    property: "is_muted",
                    value: !sub.is_muted,
                });
                e.stopPropagation();
            });

            // Unsubscribe
            $popper.on("click", ".popover_sub_unsub_button", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);
                stream_settings_components.sub_or_unsub(sub);
                e.preventDefault();
                e.stopPropagation();
            });

            $popper.on("click", ".copy_stream_link", (e) => {
                assert(e.currentTarget instanceof HTMLElement);
                clipboard_handler.popover_copy_link_to_clipboard(instance, $(e.currentTarget));
            });
        },
        onHidden(instance) {
            hide_stream_popover(instance);
        },
    });
}

async function get_message_placement_from_server(
    current_stream_id: number,
    topic_name: string,
    current_message_id: number,
): Promise<"first" | "intermediate" | "last"> {
    return new Promise((resolve) => {
        message_edit.is_message_oldest_or_newest(
            current_stream_id,
            topic_name,
            current_message_id,
            (is_oldest, is_newest) => {
                if (is_oldest) {
                    resolve("first");
                } else if (is_newest) {
                    resolve("last");
                } else {
                    resolve("intermediate");
                }
            },
        );
    });
}

async function get_message_placement_in_conversation(
    current_stream_id: number,
    topic_name: string,
    current_message_id: number,
): Promise<"first" | "intermediate" | "last"> {
    assert(message_lists.current !== undefined);
    // First we check if the placement of the message can be determined
    // in the current message list. This allows us to avoid a server call
    // in most cases.

    if (message_lists.current.data.filter.contains_no_partial_conversations()) {
        // Next we check if we are in a conversation view. If we are
        // in a conversation view, we check if the message is the
        // first or the last message in the current view. If not, we
        // can conclude that the message is an intermediate message.
        //
        // It's safe to assume message_lists.current.data is non-empty, because
        // current_message_id must be present in it.
        if (message_lists.current.data.filter.is_conversation_view()) {
            if (
                message_lists.current.data.fetch_status.has_found_oldest() &&
                message_lists.current.data.first()?.id === current_message_id
            ) {
                return "first";
            } else if (
                message_lists.current.data.fetch_status.has_found_newest() &&
                message_lists.current.data.last()?.id === current_message_id
            ) {
                return "last";
            }
            return "intermediate";
        }

        // If we are not in a conversation view, but still know
        // the view contains the entire conversation, we check if
        // we can find the adjacent messages in the current view
        // through which we can determine if the message is an
        // intermediate message or not.
        const msg_list = message_lists.current.data.all_messages();
        let found_newer_matching_message = false;
        let found_older_matching_message = false;
        const current_dict = {
            stream_id: current_stream_id,
            topic: topic_name,
        };

        for (let i = msg_list.length - 1; i >= 0; i -= 1) {
            const message = msg_list[i];
            if (message?.type === "stream" && util.same_stream_and_topic(current_dict, message)) {
                if (message.id > current_message_id) {
                    found_newer_matching_message = true;
                } else if (message.id < current_message_id) {
                    found_older_matching_message = true;
                }

                if (found_newer_matching_message && found_older_matching_message) {
                    return "intermediate";
                }
            }
        }

        if (
            message_lists.current.data.fetch_status.has_found_newest() &&
            !found_newer_matching_message
        ) {
            return "last";
        }
        if (
            message_lists.current.data.fetch_status.has_found_oldest() &&
            !found_older_matching_message
        ) {
            return "first";
        }
    }

    // In case we are unable to determine the placement of the message
    // in the current message list, we make a server call to determine
    // the placement.
    return await get_message_placement_from_server(
        current_stream_id,
        topic_name,
        current_message_id,
    );
}

export async function build_move_topic_to_stream_popover(
    current_stream_id: number,
    topic_name: string,
    only_topic_edit: boolean,
    message?: Message,
): Promise<void> {
    const current_stream_name = sub_store.get(current_stream_id)!.name;
    const stream = sub_store.get(current_stream_id);
    assert(stream !== undefined);
    const topic_display_name = util.get_final_topic_display_name(topic_name);
    const empty_string_topic_display_name = util.get_final_topic_display_name("");
    const is_empty_string_topic = topic_name === "";
    const args: {
        topic_name: string;
        empty_string_topic_display_name: string;
        current_stream_id: number;
        notify_new_thread: boolean;
        notify_old_thread: boolean;
        from_message_actions_popover: boolean;
        only_topic_edit: boolean;
        disable_topic_input?: boolean;
        message_placement?: "first" | "intermediate" | "last";
        stream: sub_store.StreamSubscription | undefined;
        max_topic_length: number;
    } = {
        topic_name,
        empty_string_topic_display_name,
        current_stream_id,
        stream,
        notify_new_thread: message_edit.notify_new_thread_default,
        notify_old_thread: message_edit.notify_old_thread_default,
        from_message_actions_popover: message !== undefined,
        only_topic_edit,
        max_topic_length: realm.max_topic_length,
    };

    // When the modal is opened for moving the whole topic from left sidebar,
    // we do not have any message object and so we disable the stream input
    // based on the can_move_messages_between_channels_group setting and topic
    // input based on can_move_messages_between_topics_group. In other cases, message object is
    // available and thus we check the time-based permissions as well in the
    // below if block to enable or disable the stream and topic input.
    let disable_stream_input = !stream_data.user_can_move_messages_out_of_channel(stream);
    args.disable_topic_input = !stream_data.user_can_move_messages_within_channel(stream);

    let modal_heading;
    if (only_topic_edit) {
        modal_heading = $t_html(
            {defaultMessage: "Rename <z-stream-or-topic></z-stream-or-topic>"},
            {
                "z-stream-or-topic": () =>
                    render_inline_stream_or_topic_reference({
                        topic_display_name,
                        is_empty_string_topic,
                        stream,
                        show_colored_icon: true,
                    }),
            },
        );
    } else {
        modal_heading = $t_html(
            {defaultMessage: "Move <z-stream-or-topic></z-stream-or-topic>"},
            {
                "z-stream-or-topic": () =>
                    render_inline_stream_or_topic_reference({
                        topic_display_name,
                        is_empty_string_topic,
                        stream,
                        show_colored_icon: true,
                    }),
            },
        );
    }

    if (message !== undefined) {
        modal_heading = $t_html(
            {defaultMessage: "Move messages from <z-stream-or-topic></z-stream-or-topic>"},
            {
                "z-stream-or-topic": () =>
                    render_inline_stream_or_topic_reference({
                        stream,
                        topic_display_name,
                        is_empty_string_topic,
                        show_colored_icon: true,
                    }),
            },
        );
        // We disable topic input only for modal is opened from the message actions
        // popover and not when moving the whole topic from left sidebar. This is
        // because topic editing permission depend on message and we do not have
        // any message object when opening the modal and the first message of
        // topic is fetched from the server after clicking submit.
        // Though, this will be changed soon as we are going to make topic
        // edit permission independent of message.

        // We potentially got to this function by clicking a button that implied the
        // user would be able to move their message.  Give a little bit of buffer in
        // case the button has been around for a bit, e.g. we show the
        // move_message_button (hovering plus icon) as long as the user would have
        // been able to click it at the time the mouse entered the message_row. Also
        // a buffer in case their computer is slow, or stalled for a second, etc
        // If you change this number also change edit_limit_buffer in
        // zerver.actions.message_edit.check_update_message
        const move_limit_buffer = 5;
        args.disable_topic_input = !message_edit.is_topic_editable(message, move_limit_buffer);
        disable_stream_input = !message_edit.is_stream_editable(message, move_limit_buffer);

        // If message is in a search view, default to "move only this message" option,
        // same as if it were the last message in any view.
        if (narrow_state.is_search_view()) {
            args.message_placement = "last";
        }
        // Else, default option is based on the message placement in the view.
        else {
            args.message_placement = await get_message_placement_in_conversation(
                current_stream_id,
                topic_name,
                message.id,
            );
        }
    }

    const params_schema = z.object({
        current_stream_id: z.string(),
        new_topic_name: z.optional(z.string()),
        old_topic_name: z.string(),
        propagate_mode: z.optional(z.enum(["change_one", "change_later", "change_all"])),
        send_notification_to_new_thread: z.optional(z.literal("on")),
        send_notification_to_old_thread: z.optional(z.literal("on")),
    });

    function get_params_from_form(): z.output<typeof params_schema> {
        return params_schema.parse(
            Object.fromEntries(
                $("#move_topic_form")
                    .serializeArray()
                    .map(({name, value}) => [name, value]),
            ),
        );
    }

    function update_submit_button_disabled_state(select_stream_id: number): void {
        const params = get_params_from_form();
        const current_stream_id = Number.parseInt(params.current_stream_id, 10);
        const new_topic_name = params.new_topic_name?.trim();
        const old_topic_name = params.old_topic_name.trim();

        // Unlike most topic comparisons in Zulip, we intentionally do
        // a case-sensitive comparison, since adjusting the
        // capitalization of a topic is a valid operation.
        // new_topic_name can be undefined when the new topic input is
        // disabled in case when user does not have permission to edit
        // topic and thus submit button is disabled if stream is also
        // not changed.
        let is_disabled = false;
        if (
            !stream_data.can_use_empty_topic(select_stream_id) &&
            (new_topic_name === "" || new_topic_name === "(no topic)")
        ) {
            is_disabled = true;
        }
        if (
            current_stream_id === select_stream_id &&
            (new_topic_name === undefined || new_topic_name === old_topic_name)
        ) {
            is_disabled = true;
        }
        util.the($<HTMLButtonElement>("#move_topic_modal button.dialog_submit_button")).disabled =
            is_disabled;
    }

    let curr_selected_stream: number;

    function get_messages_to_be_moved(
        propagate_mode: string,
        selected_message: Message | undefined,
    ): Message[] {
        const all_locally_cached_conversation_messages = message_util.get_loaded_messages_in_topic(
            current_stream_id,
            topic_name,
        );

        // It's move-topic modal, so no message is selected.
        if (selected_message === undefined) {
            return all_locally_cached_conversation_messages;
        }

        // Move only selected message.
        if (propagate_mode === "change_one") {
            return [selected_message];
        }

        // Move selected message and all its following messages.
        if (propagate_mode === "change_later") {
            return all_locally_cached_conversation_messages.filter(
                (msg) => msg.id >= selected_message.id,
            );
        }

        // Move all messages in topic.
        return all_locally_cached_conversation_messages;
    }

    // Warn if any sender of the messages being moved is NOT subscribed
    // to the destination stream.
    async function warn_unsubscribed_participants(selected_propagate_mode: string): Promise<void> {
        $("#move_topic_modal .unsubscribed-participants-warning").remove();

        const destination_stream_id = stream_widget_value;

        // Do nothing if it's the same stream.
        if (destination_stream_id === undefined || destination_stream_id === current_stream_id) {
            return;
        }

        // Only participants who sent the messages being moved should appear in the banner,
        // so we fetch those messages first.
        const messages_to_be_moved = get_messages_to_be_moved(selected_propagate_mode, message);

        const active_human_participant_ids = new ConversationParticipants(
            messages_to_be_moved,
        ).visible();

        const unsubscribed_participant_ids: number[] = [];
        for (const user_id of active_human_participant_ids) {
            const is_subscribed = await peer_data.maybe_fetch_is_user_subscribed(
                destination_stream_id,
                user_id,
                false,
            );
            if (!is_subscribed) {
                unsubscribed_participant_ids.push(user_id);
            }
        }

        if (destination_stream_id !== curr_selected_stream) {
            // If user selects another stream after the above await finishes
            // but before the function finishes, we should NOT show
            // the banner, as it would belong to the previously selected stream.
            return;
        }

        const unsubscribed_participants_count = unsubscribed_participant_ids.length;

        if (unsubscribed_participants_count === 0) {
            // This is true in the following cases, for all of which we do nothing :
            // 1- Conversation (topic) has no participants.
            // 2- All participants are subscribed to the destination stream.
            return;
        }

        const participant_names = unsubscribed_participant_ids.map(
            (user_id) => people.get_user_by_id_assert_valid(user_id).full_name,
        );
        const unsubscribed_participant_formatted_names_list =
            util.format_array_as_list_with_highlighted_elements(
                participant_names,
                "long",
                "conjunction",
            );

        const destination_stream = stream_data.get_sub_by_id(destination_stream_id)!;
        const can_subscribe_other_users = stream_data.can_subscribe_others(destination_stream);
        const few_unsubscribed_participants = unsubscribed_participants_count <= 5;

        const context = {
            banner_type: compose_banner.WARNING,
            classname: "unsubscribed-participants-warning",
            button_text: can_subscribe_other_users
                ? few_unsubscribed_participants
                    ? $t({defaultMessage: "Subscribe them"})
                    : $t({defaultMessage: "Subscribe all of them"})
                : null,
            hide_close_button: true,
            stream: destination_stream,
            selected_propagate_mode,
            unsubscribed_participant_formatted_names_list,
            unsubscribed_participants_count,
            few_unsubscribed_participants,
        };

        const warning_banner = render_unsubscribed_participants_warning_banner(context);
        $("#move_topic_modal .simplebar-content").prepend($(warning_banner));

        $(
            "#move_topic_modal .unsubscribed-participants-warning .main-view-banner-action-button",
        ).on("click", (event) => {
            event.preventDefault();

            function success(): void {
                $(event.target).parents(".main-view-banner").remove();
            }

            function xhr_failure(xhr: JQuery.jqXHR): void {
                $(event.target).parents(".main-view-banner").remove();
                ui_report.error(
                    $t_html({defaultMessage: "Failed to subscribe participants"}),
                    xhr,
                    $("#move_topic_modal #dialog_error"),
                );
            }

            subscriber_api.add_user_ids_to_stream(
                unsubscribed_participant_ids,
                destination_stream,
                true,
                success,
                xhr_failure,
            );
        });
    }

    function move_topic(): void {
        const params = get_params_from_form();

        const old_topic_name = params.old_topic_name.trim();
        let select_stream_id;
        if (only_topic_edit) {
            select_stream_id = undefined;
        } else {
            select_stream_id = stream_widget_value;
        }

        let new_topic_name = params.new_topic_name;
        const send_notification_to_new_thread = params.send_notification_to_new_thread === "on";
        const send_notification_to_old_thread = params.send_notification_to_old_thread === "on";
        const current_stream_id = Number.parseInt(params.current_stream_id, 10);

        // Can only move to empty topic if topics are disabled in the destination channel.
        if (stream_data.is_empty_topic_only_channel(select_stream_id ?? current_stream_id)) {
            new_topic_name = "";
        }

        if (new_topic_name !== undefined) {
            // new_topic_name can be undefined when the new topic input is disabled when
            // user does not have permission to edit topic.
            new_topic_name = new_topic_name.trim();
        }
        if (old_topic_name === new_topic_name) {
            // We use `undefined` to tell the server that
            // there has been no change in the topic name.
            new_topic_name = undefined;
        }
        if (select_stream_id === current_stream_id) {
            // We use `undefined` to tell the server that
            // there has been no change in stream. This is
            // important for cases when changing stream is
            // not allowed or when changes other than
            // stream-change has been made.
            select_stream_id = undefined;
        }

        let propagate_mode = "change_all";
        if (message !== undefined) {
            // We already have the message_id here which means that modal is opened using
            // message popover.
            assert(params.propagate_mode !== undefined);
            propagate_mode = params.propagate_mode;
            const toast_params =
                propagate_mode === "change_one"
                    ? {
                          new_stream_id: select_stream_id ?? current_stream_id,
                          new_topic_name: new_topic_name ?? old_topic_name,
                      }
                    : undefined;
            message_edit.move_topic_containing_message_to_stream(
                message.id,
                select_stream_id,
                new_topic_name,
                send_notification_to_new_thread,
                send_notification_to_old_thread,
                propagate_mode,
                toast_params,
            );
            return;
        }

        dialog_widget.show_dialog_spinner();
        message_edit.with_first_message_id(
            current_stream_id,
            old_topic_name,
            (message_id) => {
                if (message_id === undefined) {
                    // There are no messages in the given topic, so we show an error banner
                    // and return, preventing any attempts to move a non-existent topic.
                    dialog_widget.hide_dialog_spinner();
                    ui_report.client_error(
                        $t_html({defaultMessage: "There are no messages to move."}),
                        $("#move_topic_modal #dialog_error"),
                    );
                    return;
                }
                message_edit.move_topic_containing_message_to_stream(
                    message_id,
                    select_stream_id,
                    new_topic_name,
                    send_notification_to_new_thread,
                    send_notification_to_old_thread,
                    propagate_mode,
                );
            },
            (xhr) => {
                dialog_widget.hide_dialog_spinner();
                ui_report.error(
                    $t_html({defaultMessage: "Error moving topic"}),
                    xhr,
                    $("#move_topic_modal #dialog_error"),
                );
            },
        );
    }

    function set_stream_topic_typeahead(): void {
        const $topic_input = $<HTMLInputElement>("#move_topic_form input.move_messages_edit_topic");
        assert(stream_widget_value !== undefined);
        const new_stream_name = sub_store.get(stream_widget_value)!.name;
        move_topic_to_stream_topic_typeahead?.unlisten();
        move_topic_to_stream_topic_typeahead = composebox_typeahead.initialize_topic_edit_typeahead(
            $topic_input,
            new_stream_name,
            false,
        );
    }

    function show_topic_already_exists_warning(): boolean {
        // Don't show warning if the submit button is disabled.
        if ($("#move_topic_modal .dialog_submit_button").expectOne().prop("disabled")) {
            return false;
        }
        // Don't show warning if we are only moving one message.
        if ($("#move_topic_modal select.message_edit_topic_propagate").val() === "change_one") {
            return false;
        }
        let {new_topic_name} = get_params_from_form();

        const current_stream = stream_data.get_sub_by_id(current_stream_id);
        const selected_stream = stream_data.get_sub_by_id(
            curr_selected_stream || current_stream_id,
        );

        assert(current_stream !== undefined);
        assert(selected_stream !== undefined);

        // Users can only edit topic if they have either of these permissions:
        //   1) organization-level permission to edit topics
        //   2) channel-level permission to edit topics in the current channel
        //   3) channel-level permission to edit topics in the selected channel
        if (
            !stream_data.user_can_move_messages_within_channel(current_stream) &&
            !stream_data.user_can_move_messages_within_channel(selected_stream)
        ) {
            // new_topic_name is undefined since the new topic input is disabled when
            // user does not have permission to edit topic.
            new_topic_name = args.topic_name;
        }

        if (stream_data.is_empty_topic_only_channel(selected_stream.stream_id)) {
            new_topic_name = "";
        }

        assert(new_topic_name !== undefined);
        // Don't show warning for empty topic as the user is probably
        // about to type a new topic name. Note that if topics are
        // mandatory, then the submit button is disabled, which returns
        // early above.
        if (new_topic_name === "" || new_topic_name === "(no topic)") {
            return false;
        }
        let stream_id: number;
        if (stream_widget_value === undefined) {
            // Set stream_id to current_stream_id since the user is not
            // allowed to edit the stream in topic-edit only UI.
            stream_id = current_stream_id;
        } else {
            stream_id = stream_widget_value;
        }
        const stream_topics = stream_topic_history
            .get_recent_topic_names(stream_id)
            .map((topic) => topic.toLowerCase());
        if (stream_topics.includes(new_topic_name.trim().toLowerCase())) {
            return true;
        }
        return false;
    }

    function maybe_show_topic_already_exists_warning(): void {
        const $move_topic_warning_container = $("#move_topic_modal .move_topic_warning_container");
        if (show_topic_already_exists_warning()) {
            $move_topic_warning_container.html(
                render_topic_already_exists_warning_banner({
                    banner_type: compose_banner.WARNING,
                    hide_close_button: true,
                    classname: "topic_already_exists_warning",
                }),
            );
            $move_topic_warning_container.show();
        } else {
            $move_topic_warning_container.hide();
        }
    }

    function render_selected_stream(): void {
        assert(stream_widget_value !== undefined);
        const stream = stream_data.get_sub_by_id(stream_widget_value);
        if (stream === undefined) {
            $("#move_topic_to_stream_widget .dropdown_widget_value").text(
                $t({defaultMessage: "Select a channel"}),
            );
        } else {
            $("#move_topic_to_stream_widget .dropdown_widget_value").html(
                render_inline_decorated_channel_name({stream, show_colored_icon: true}),
            );
        }
    }

    function disable_topic_input_if_topics_are_disabled_in_channel(stream_id: number): void {
        const $topic_input = $<HTMLInputElement>("#move_topic_form input.move_messages_edit_topic");
        if (stream_data.is_empty_topic_only_channel(stream_id)) {
            $topic_input.val("");
            $topic_input.prop("disabled", true);
            $topic_input.addClass("empty-topic-only");
            update_topic_input_placeholder();
        } else {
            // Removes tooltip if topics are allowed.
            $topic_input.removeClass("empty-topic-only");
        }
    }

    function move_topic_on_update(event: JQuery.ClickEvent, dropdown: {hide: () => void}): void {
        stream_widget_value = Number.parseInt($(event.currentTarget).attr("data-unique-id")!, 10);
        const $topic_input = $<HTMLInputElement>("#move_topic_form input.move_messages_edit_topic");
        curr_selected_stream = stream_widget_value;
        const params = get_params_from_form();
        const current_stream = stream_data.get_sub_by_id(current_stream_id);
        const selected_stream = stream_data.get_sub_by_id(
            curr_selected_stream || current_stream_id,
        );

        assert(current_stream !== undefined);
        assert(selected_stream !== undefined);

        // Enable topic editing only if the user has at least one of these permissions:
        //   1) organization-level permission to edit topics
        //   2) channel-level permission to edit topics in the current channel
        //   3) channel-level permission to edit topics in the selected channel
        // If none apply, disable the input and reset it to the original topic name.
        if (
            stream_data.user_can_move_messages_within_channel(current_stream) ||
            stream_data.user_can_move_messages_within_channel(selected_stream)
        ) {
            $topic_input.prop("disabled", false);
        } else {
            $topic_input.val(params.old_topic_name);
            $topic_input.prop("disabled", true);
        }

        disable_topic_input_if_topics_are_disabled_in_channel(selected_stream.stream_id);

        update_submit_button_disabled_state(stream_widget_value);
        set_stream_topic_typeahead();
        render_selected_stream();
        maybe_show_topic_already_exists_warning();
        update_topic_input_placeholder();
        const selected_propagate_mode = String($("#message_move_select_options").val());
        void warn_unsubscribed_participants(selected_propagate_mode);

        dropdown.hide();
        event.preventDefault();
        event.stopPropagation();

        // Move focus to the topic input after a new stream is selected
        // if it is not disabled.
        if (!$topic_input.prop("disabled")) {
            $topic_input.trigger("focus");
        }
    }

    // The following logic is correct only when
    // both message_lists.current.data.fetch_status.has_found_newest
    // and message_lists.current.data.fetch_status.has_found_oldest are true;
    // otherwise, we cannot be certain of the correct count.
    function get_count_of_messages_to_be_moved(
        selected_option: string,
        message_id?: number,
    ): number {
        if (selected_option === "change_one") {
            return 1;
        }
        if (selected_option === "change_later" && message_id !== undefined) {
            return message_util.get_count_of_messages_in_topic_sent_after_current_message(
                current_stream_id,
                topic_name,
                message_id,
            );
        }
        return message_util.get_loaded_messages_in_topic(current_stream_id, topic_name).length;
    }

    function update_move_messages_count_text(selected_option: string, message_id?: number): void {
        const message_move_count = get_count_of_messages_to_be_moved(selected_option, message_id);
        const is_topic_narrowed = narrow_state.narrowed_by_topic_reply();
        const is_stream_narrowed = narrow_state.narrowed_by_stream_reply();
        const is_same_stream = narrow_state.stream_id() === current_stream_id;
        const is_same_topic = narrow_state.topic() === topic_name;

        const can_have_exact_count_in_narrow =
            (is_stream_narrowed && is_same_stream) ||
            (is_topic_narrowed && is_same_stream && is_same_topic);
        let exact_message_count = false;
        if (selected_option === "change_one") {
            exact_message_count = true;
        } else if (can_have_exact_count_in_narrow) {
            const has_found_newest = message_lists.current?.data.fetch_status.has_found_newest();
            const has_found_oldest = message_lists.current?.data.fetch_status.has_found_oldest();

            if (selected_option === "change_later" && has_found_newest) {
                exact_message_count = true;
            }
            if (selected_option === "change_all" && has_found_newest && has_found_oldest) {
                exact_message_count = true;
            }
        }

        let message_text;
        if (exact_message_count) {
            message_text = $t(
                {
                    defaultMessage:
                        "{count, plural, one {# message} other {# messages}} will be moved.",
                },
                {count: message_move_count},
            );
        } else {
            message_text = $t(
                {
                    defaultMessage:
                        "At least {count, plural, one {# message} other {# messages}} will be moved.",
                },
                {count: message_move_count},
            );
        }

        $("#move_messages_count").text(message_text);
    }

    function update_topic_input_placeholder(): void {
        const $topic_not_mandatory_placeholder = $(".move-topic-new-topic-placeholder");
        const $topic_input = $<HTMLInputElement>("#move_topic_form input.move_messages_edit_topic");
        const topic_input_value = $topic_input.val();
        const has_input_focus = $topic_input.is(":focus");

        // reset
        $topic_input.attr("placeholder", "");
        $topic_input.removeClass("empty-topic-display");
        $topic_not_mandatory_placeholder.removeClass("move-topic-new-topic-placeholder-visible");
        update_clear_move_topic_button_state();

        if (topic_input_value !== "" || !stream_data.can_use_empty_topic(stream_widget_value)) {
            // Don't add any placeholder if either topic input is not empty or empty topic
            // is disabled in the channel.
            return;
        }

        if (has_input_focus) {
            $topic_not_mandatory_placeholder.addClass("move-topic-new-topic-placeholder-visible");
        } else {
            $topic_input.attr("placeholder", empty_string_topic_display_name);
            $topic_input.addClass("empty-topic-display");
        }
    }

    function setup_resize_observer($topic_input: JQuery<HTMLInputElement>): void {
        // Update position of topic typeahead because showing/hiding the
        // "topic already exists" warning changes the size of the modal.
        const update_topic_typeahead_position = new ResizeObserver((_entries) => {
            requestAnimationFrame(() => {
                $topic_input.trigger(new $.Event("typeahead.refreshPosition"));
            });
        });
        const move_topic_form = document.querySelector("#move_topic_form");
        if (move_topic_form) {
            update_topic_typeahead_position.observe(move_topic_form);
        }
    }

    function update_clear_move_topic_button_state(): void {
        const $clear_topic_name_button = $("#clear_move_topic_new_topic_name");
        const topic_input_value = $("input#move-topic-new-topic-name").val();
        if (topic_input_value === "" || $("input#move-topic-new-topic-name").prop("disabled")) {
            $clear_topic_name_button.css("visibility", "hidden");
        } else {
            $clear_topic_name_button.css("visibility", "visible");
        }
    }

    function move_topic_post_render(): void {
        $("#move_topic_modal .dialog_submit_button").prop("disabled", true);
        $("#move_topic_modal .move_topic_warning_container").hide();

        const $topic_input = $<HTMLInputElement>("#move_topic_form input.move_messages_edit_topic");
        move_topic_to_stream_topic_typeahead = composebox_typeahead.initialize_topic_edit_typeahead(
            $topic_input,
            current_stream_name,
            false,
        );

        const $topic_not_mandatory_placeholder = $(".move-topic-new-topic-placeholder");

        if (topic_name === "" && stream_data.can_use_empty_topic(current_stream_id)) {
            $topic_not_mandatory_placeholder.addClass("move-topic-new-topic-placeholder-visible");
        }

        $topic_input.on("focus", () => {
            update_topic_input_placeholder();

            $topic_input.one("blur", () => {
                update_topic_input_placeholder();
            });
        });

        setup_resize_observer($topic_input);
        update_clear_move_topic_button_state();

        $("#clear_move_topic_new_topic_name").on("click", (e) => {
            e.stopPropagation();
            const $topic_input = $("#move-topic-new-topic-name").expectOne();
            $topic_input.val("");
            $topic_input.trigger("input").trigger("focus");
            move_topic_to_stream_topic_typeahead?.hide();
        });

        stream_widget_value = current_stream_id;
        if (only_topic_edit) {
            // Set select_stream_id to current_stream_id since user is not allowed
            // to edit stream in topic-edit only UI.
            const select_stream_id = current_stream_id;
            $topic_input.on("input", () => {
                update_submit_button_disabled_state(select_stream_id);
                maybe_show_topic_already_exists_warning();
                update_topic_input_placeholder();
            });
            return;
        }

        const streams_list_options = (): dropdown_widget.Option[] =>
            stream_data.get_streams_for_move_messages_widget().filter(({stream}) => {
                if (stream.stream_id === current_stream_id) {
                    return true;
                }
                const current_stream = stream_data.get_sub_by_id(current_stream_id);
                assert(current_stream !== undefined);
                // If the user can't edit the topic, it is not possible for them to make
                // following kind of moves:
                //  1) messages from empty topics to channels where empty topics are disabled.
                //  2) messages from named topics to channels where topics are disabled.
                // So we filter them out here.
                if (
                    !stream_data.user_can_move_messages_within_channel(current_stream) &&
                    !stream_data.user_can_move_messages_within_channel(stream)
                ) {
                    if (
                        topic_name !== "" &&
                        stream_data.is_empty_topic_only_channel(stream.stream_id)
                    ) {
                        return false;
                    }
                    if (topic_name === "" && !stream_data.can_use_empty_topic(stream.stream_id)) {
                        return false;
                    }
                }
                return stream_data.can_post_messages_in_stream(stream);
            });

        new dropdown_widget.DropdownWidget({
            widget_name: "move_topic_to_stream",
            get_options: streams_list_options,
            item_click_callback: move_topic_on_update,
            $events_container: $("#move_topic_modal"),
            tippy_props: {
                // Show dropdown search input below stream selection button.
                offset: [0, 2],
            },
        }).setup();

        render_selected_stream();
        $("#move_topic_to_stream_widget").prop("disabled", disable_stream_input);
        $topic_input.on("input", () => {
            assert(stream_widget_value !== undefined);
            update_submit_button_disabled_state(stream_widget_value);
            maybe_show_topic_already_exists_warning();
            update_topic_input_placeholder();
        });

        update_topic_input_placeholder();

        if (!args.from_message_actions_popover) {
            update_move_messages_count_text("change_all");
        } else {
            // Generate unique key for this conversation
            const conversation_key = `${current_stream_id}_${topic_name}`;
            let selected_option = String($("#message_move_select_options").val());

            // If a user has changed the smart defaults of `propagate_mode` to "change_one", we
            // remember that forced change and apply the same default for `propagate_mode` next
            // time when the user tries to move the message of the same topic to save the time
            // of user manually selecting "change_one" every time.
            const previously_used_propagate_mode =
                last_propagate_mode_for_conversation.get(conversation_key);
            if (previously_used_propagate_mode === "change_one") {
                selected_option = "change_one";
                $("#message_move_select_options").val(selected_option);
            }

            update_move_messages_count_text(selected_option, message?.id);

            $("#message_move_select_options").on("change", function () {
                selected_option = String($(this).val());
                last_propagate_mode_for_conversation.set(conversation_key, selected_option);
                void warn_unsubscribed_participants(selected_option);
                maybe_show_topic_already_exists_warning();
                update_move_messages_count_text(selected_option, message?.id);
            });
        }
        disable_topic_input_if_topics_are_disabled_in_channel(current_stream_id);
    }

    function focus_on_move_modal_render(): void {
        if (!args.disable_topic_input) {
            ui_util.place_caret_at_end(util.the($(".move_messages_edit_topic")));
        }
    }

    dialog_widget.launch({
        html_heading: modal_heading,
        html_body: render_move_topic_to_stream(args),
        html_submit_button: $t_html({defaultMessage: "Confirm"}),
        id: "move_topic_modal",
        form_id: "move_topic_form",
        on_click: move_topic,
        loading_spinner: true,
        on_shown: focus_on_move_modal_render,
        on_hidden() {
            move_topic_to_stream_topic_typeahead = undefined;
        },
        post_render: move_topic_post_render,
    });
}

export function initialize(): void {
    $("#stream_filters").on("click", ".stream-sidebar-menu-icon", function (this: HTMLElement, e) {
        e.preventDefault();
        const $stream_li = $(this).parents("li");
        const stream_id = elem_to_stream_id($stream_li);

        build_stream_popover({
            elt: this,
            stream_id,
        });

        e.stopPropagation();
    });

    $("body").on("click", ".inbox-stream-menu", function (this: HTMLElement, e) {
        const stream_id = Number.parseInt($(this).attr("data-stream-id")!, 10);

        build_stream_popover({
            elt: this,
            stream_id,
        });

        e.stopPropagation();
    });
}

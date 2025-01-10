import ClipboardJS from "clipboard";
import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";
import {z} from "zod";

import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";
import render_inline_stream_or_topic_reference from "../templates/inline_stream_or_topic_reference.hbs";
import render_move_topic_to_stream from "../templates/move_topic_to_stream.hbs";
import render_left_sidebar_stream_actions_popover from "../templates/popovers/left_sidebar/left_sidebar_stream_actions_popover.hbs";

import * as blueslip from "./blueslip.ts";
import type {Typeahead} from "./bootstrap_typeahead.ts";
import * as browser_history from "./browser_history.ts";
import * as composebox_typeahead from "./composebox_typeahead.ts";
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
import * as popover_menus from "./popover_menus.ts";
import {left_sidebar_tippy_options} from "./popover_menus.ts";
import {web_channel_default_view_values} from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_api from "./stream_settings_api.ts";
import * as stream_settings_components from "./stream_settings_components.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as sub_store from "./sub_store.ts";
import * as ui_report from "./ui_report.ts";
import * as ui_util from "./ui_util.ts";
import * as unread_ops from "./unread_ops.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

// In this module, we manage stream popovers
// that pop up from the left sidebar.
let stream_widget_value: number | undefined;
let move_topic_to_stream_topic_typeahead: Typeahead<string> | undefined;

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

    const stream_hash = hash_util.by_stream_url(stream_id);
    const show_go_to_channel_feed =
        user_settings.web_channel_default_view !==
        web_channel_default_view_values.channel_feed.code;
    const content = render_left_sidebar_stream_actions_popover({
        stream: {
            ...sub_store.get(stream_id),
            url: browser_history.get_full_url(stream_hash),
        },
        show_go_to_channel_feed,
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

            // Stream settings
            $popper.on("click", ".open_stream_settings", (e) => {
                const sub = stream_popover_sub(e);
                hide_stream_popover(instance);

                // Admin can change any stream's name & description either stream is public or
                // private, subscribed or unsubscribed.
                const can_change_name_description = stream_data.can_edit_description(sub);
                const can_change_stream_permissions = stream_data.can_change_permissions(sub);
                let stream_edit_hash = hash_util.channels_settings_edit_url(sub, "general");
                if (!can_change_stream_permissions && !can_change_name_description) {
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

            new ClipboardJS(util.the($popper.find(".copy_stream_link"))).on("success", () => {
                popover_menus.hide_current_popover_if_visible(instance);
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

    if (message_lists.current.data.filter.supports_collapsing_recipients()) {
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
    const topic_display_name = util.get_final_topic_display_name(topic_name);
    const is_empty_string_topic = topic_name === "";
    const args: {
        topic_name: string;
        topic_display_name: string;
        is_empty_string_topic: boolean;
        current_stream_id: number;
        notify_new_thread: boolean;
        notify_old_thread: boolean;
        from_message_actions_popover: boolean;
        only_topic_edit: boolean;
        disable_topic_input?: boolean;
        message_placement?: "first" | "intermediate" | "last";
        stream: sub_store.StreamSubscription | undefined;
    } = {
        topic_name,
        topic_display_name,
        is_empty_string_topic,
        current_stream_id,
        stream,
        notify_new_thread: message_edit.notify_new_thread_default,
        notify_old_thread: message_edit.notify_old_thread_default,
        from_message_actions_popover: message !== undefined,
        only_topic_edit,
    };

    // When the modal is opened for moving the whole topic from left sidebar,
    // we do not have any message object and so we disable the stream input
    // based on the can_move_messages_between_channels_group setting and topic
    // input based on can_move_messages_between_topics_group. In other cases, message object is
    // available and thus we check the time-based permissions as well in the
    // below if block to enable or disable the stream and topic input.
    let disable_stream_input = !settings_data.user_can_move_messages_between_streams();
    args.disable_topic_input = !settings_data.user_can_move_messages_to_another_topic();

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
        new_topic_name: z.string().optional(),
        old_topic_name: z.string(),
        propagate_mode: z.enum(["change_one", "change_later", "change_all"]).optional(),
        send_notification_to_new_thread: z.literal("on").optional(),
        send_notification_to_old_thread: z.literal("on").optional(),
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
        const {current_stream_id, new_topic_name, old_topic_name} = get_params_from_form();

        // Unlike most topic comparisons in Zulip, we intentionally do
        // a case-sensitive comparison, since adjusting the
        // capitalization of a topic is a valid operation.
        // new_topic_name can be undefined when the new topic input is
        // disabled in case when user does not have permission to edit
        // topic and thus submit button is disabled if stream is also
        // not changed.
        util.the($<HTMLButtonElement>("#move_topic_modal button.dialog_submit_button")).disabled =
            Number.parseInt(current_stream_id, 10) === select_stream_id &&
            (new_topic_name === undefined || new_topic_name.trim() === old_topic_name.trim());
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

    function render_selected_stream(): void {
        assert(stream_widget_value !== undefined);
        const stream = stream_data.get_sub_by_id(stream_widget_value);
        if (stream === undefined) {
            $("#move_topic_to_stream_widget .dropdown_widget_value").text(
                $t({defaultMessage: "Select a channel"}),
            );
        } else {
            $("#move_topic_to_stream_widget .dropdown_widget_value").html(
                render_inline_decorated_stream_name({stream, show_colored_icon: true}),
            );
        }
    }

    function move_topic_on_update(event: JQuery.ClickEvent, dropdown: {hide: () => void}): void {
        stream_widget_value = Number.parseInt($(event.currentTarget).attr("data-unique-id")!, 10);

        update_submit_button_disabled_state(stream_widget_value);
        set_stream_topic_typeahead();
        render_selected_stream();

        dropdown.hide();
        event.preventDefault();
        event.stopPropagation();

        // Move focus to the topic input after a new stream is selected.
        $("#move_topic_form .move_messages_edit_topic").trigger("focus");
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
        return message_util.get_messages_in_topic(current_stream_id, topic_name).length;
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

    function move_topic_post_render(): void {
        $("#move_topic_modal .dialog_submit_button").prop("disabled", true);

        const $topic_input = $<HTMLInputElement>("#move_topic_form input.move_messages_edit_topic");
        move_topic_to_stream_topic_typeahead = composebox_typeahead.initialize_topic_edit_typeahead(
            $topic_input,
            current_stream_name,
            false,
        );

        if (only_topic_edit) {
            // Set select_stream_id to current_stream_id since we user is not allowed
            // to edit stream in topic-edit only UI.
            const select_stream_id = current_stream_id;
            $topic_input.on("input", () => {
                update_submit_button_disabled_state(select_stream_id);
            });
            return;
        }

        stream_widget_value = current_stream_id;
        const streams_list_options = (): {
            name: string;
            unique_id: number;
            stream: sub_store.StreamSubscription;
        }[] =>
            stream_data.get_options_for_dropdown_widget().filter(({stream}) => {
                if (stream.stream_id === current_stream_id) {
                    return true;
                }
                return stream_data.can_post_messages_in_stream(stream);
            });

        new dropdown_widget.DropdownWidget({
            widget_name: "move_topic_to_stream",
            get_options: streams_list_options,
            item_click_callback: move_topic_on_update,
            $events_container: $("#move_topic_modal"),
            tippy_props: {
                // Overlap dropdown search input with stream selection button.
                offset: [0, -30],
            },
        }).setup();

        render_selected_stream();
        $("#move_topic_to_stream_widget").prop("disabled", disable_stream_input);
        $("#move_topic_modal .move_messages_edit_topic").on("input", () => {
            update_submit_button_disabled_state(current_stream_id);
        });

        if (!args.from_message_actions_popover) {
            update_move_messages_count_text("change_all");
        } else {
            let selected_option = String($("#message_move_select_options").val());
            update_move_messages_count_text(selected_option, message?.id);

            $("#message_move_select_options").on("change", function () {
                selected_option = String($(this).val());
                update_move_messages_count_text(selected_option, message?.id);
            });
        }
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

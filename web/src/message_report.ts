import $ from "jquery";
import assert from "minimalistic-assert";
import type * as tippy from "tippy.js";

import render_message_preview from "../templates/message_preview.hbs";
import render_report_message_modal from "../templates/report_message_modal.hbs";

import * as channel from "./channel.ts";
import * as condense from "./condense.ts";
import * as dialog_widget from "./dialog_widget.ts";
import type {Option} from "./dropdown_widget.ts";
import * as dropdown_widget from "./dropdown_widget.ts";
import {$t_html} from "./i18n.ts";
import {get_timestr} from "./message_list_view.ts";
import type {Message} from "./message_store.ts";
import * as people from "./people.ts";
import * as stream_color from "./stream_color.ts";
import * as stream_data from "./stream_data.ts";
import * as sub_store from "./sub_store.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import {toggle_user_card_popover_for_message} from "./user_card_popover.ts";
import * as util from "./util.ts";

export const message_report_type_options: Option[] = [
    {
        unique_id: "spam",
        name: $t_html({defaultMessage: "Spam"}),
    },
    {
        unique_id: "harassment",
        name: $t_html({defaultMessage: "Harassment"}),
    },
    {
        unique_id: "inappropriate",
        name: $t_html({defaultMessage: "Inappropriate"}),
    },
    {
        unique_id: "norms",
        name: $t_html({defaultMessage: "Violates community norms"}),
    },
];

type MessagePreviewRenderContext = {
    header_timestr: string;
    include_sender: boolean;
    msg: Message;
    sender_is_bot: boolean;
    should_add_guest_indicator_for_sender: boolean;
    small_avatar_url: string;
    timestr: string;
} & (
    | {
          is_empty_string_topic: boolean;
          is_stream: true;
          recipient_bar_color: string;
          stream_id: number;
          stream_name: string;
          stream_privacy_icon_color: string;
          topic_display_name: string;
      }
    | {
          is_stream: false;
          is_dm_with_self: boolean;
          recipients: string;
      }
);

function register_message_preview_click_handlers(
    message_preview_container: JQuery,
    sender_id: number,
): void {
    // This function registers click handlers and mouseover effects
    // for the message sender in the message preview container.
    // The logic here is partly from message_list_hover.ts, and
    // partly from user_card_popover.ts.

    message_preview_container.on("mouseover", ".sender_info_hover", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");
        $row.addClass("sender_info_hovered");
    });

    message_preview_container.on("mouseout", ".sender_info_hover", function (this: HTMLElement) {
        const $row = $(this).closest(".message_row");
        $row.removeClass("sender_info_hovered");
    });

    message_preview_container.on(
        "click",
        ".sender_name, .inline-profile-picture-wrapper",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            const user = people.get_by_user_id(sender_id);
            toggle_user_card_popover_for_message(this, user, sender_id, true);
        },
    );
}

function render_report_message_preview(message: Message): void {
    const $report_message_preview_container = $("#report-message-preview-container");
    const time = new Date(message.timestamp * 1000);
    const header_timestr = timerender.render_now(time).time_str;
    const include_sender = true;
    const sender_is_bot = people.sender_is_bot(message);
    const should_add_guest_indicator_for_sender = people.should_add_guest_user_indicator(
        message.sender_id,
    );
    const small_avatar_url = people.small_avatar_url(message);
    const timestr = get_timestr(message);

    let render_context: MessagePreviewRenderContext;
    if (message.type === "stream") {
        const color = stream_data.get_color(message.stream_id);
        const recipient_bar_color = stream_color.get_recipient_bar_color(color);
        const stream_id = message.stream_id;
        const stream_name = sub_store.maybe_get_stream_name(stream_id);
        const stream_privacy_icon_color = stream_color.get_stream_privacy_icon_color(color);
        assert(stream_name !== undefined);

        render_context = {
            header_timestr,
            include_sender,
            is_empty_string_topic: message.topic === "",
            is_stream: true as const,
            msg: message,
            recipient_bar_color,
            sender_is_bot,
            should_add_guest_indicator_for_sender,
            small_avatar_url,
            stream_id,
            stream_name,
            stream_privacy_icon_color,
            timestr,
            topic_display_name: util.get_final_topic_display_name(message.topic),
        };
    } else {
        assert(message.type === "private");
        const recipient_user_ids = people.pm_with_user_ids(message);
        assert(recipient_user_ids !== undefined);
        const is_dm_with_self = people.is_direct_message_conversation_with_self(recipient_user_ids);
        const recipients = people.user_ids_to_full_names_string(recipient_user_ids);

        render_context = {
            header_timestr,
            include_sender,
            is_stream: false as const,
            msg: message,
            is_dm_with_self,
            recipients,
            sender_is_bot,
            should_add_guest_indicator_for_sender,
            small_avatar_url,
            timestr,
        };
    }

    // Condense the message preview, the main motivation is to hide the
    // potentially unpleasant message content.
    const rendered_report_message_preview = render_message_preview(render_context);
    $report_message_preview_container.append($(rendered_report_message_preview));

    register_message_preview_click_handlers($report_message_preview_container, message.sender_id);

    condense.show_message_expander(
        $report_message_preview_container,
        null,
        $t_html({defaultMessage: "Show message"}),
    );

    $report_message_preview_container.on("click", ".message_expander", (e) => {
        const $content = $report_message_preview_container.find(".message_content");
        if ($content.hasClass("collapsed")) {
            $content.removeClass("collapsed");
            condense.show_message_condenser(
                $report_message_preview_container,
                null,
                $t_html({defaultMessage: "Hide message"}),
            );
        }
        e.preventDefault();
        e.stopPropagation();
    });

    $report_message_preview_container.on("click", ".message_condenser", (e) => {
        const $content = $report_message_preview_container.find(".message_content");
        if (!$content.hasClass("collapsed")) {
            $content.addClass("collapsed");
            condense.show_message_expander(
                $report_message_preview_container,
                null,
                $t_html({defaultMessage: "Show message"}),
            );
        }
        e.preventDefault();
        e.stopPropagation();
    });
}

export function show_message_report_modal(message: Message): void {
    const html_body = render_report_message_modal({});
    let report_type_dropdown_widget: dropdown_widget.DropdownWidget;

    function message_report_post_render(): void {
        render_report_message_preview(message);
        function get_message_report_types(): Option[] {
            // Keep this in sync with zerver/models/realms/Realm.REPORT_MESSAGE_REASONS
            return [
                ...message_report_type_options.toSorted(),
                {
                    unique_id: "other",
                    name: $t_html({defaultMessage: "Other reason"}),
                },
            ];
        }

        function message_report_type_click_callback(
            event: JQuery.ClickEvent,
            dropdown: tippy.Instance,
        ): void {
            report_type_dropdown_widget.render();
            $(".report-type-wrapper").trigger("input");

            dropdown.hide();
            event.preventDefault();
            event.stopPropagation();
        }

        report_type_dropdown_widget = new dropdown_widget.DropdownWidget({
            widget_name: "report_type_options",
            get_options: get_message_report_types,
            item_click_callback: message_report_type_click_callback,
            $events_container: $("#message_report_modal"),
            default_id: "spam",
            unique_id_type: "string",
        });
        report_type_dropdown_widget.setup();
        report_type_dropdown_widget.render();
    }

    function report_message(): void {
        const selected_report_type = report_type_dropdown_widget.value();
        assert(selected_report_type !== undefined);
        const report_description = $<HTMLInputElement>("#message-report-description").val()!.trim();
        if (selected_report_type === "other" && !report_description) {
            ui_report.error(
                $t_html({defaultMessage: "Please provide an explanation"}),
                undefined,
                $("#dialog_error"),
            );
            dialog_widget.hide_dialog_spinner();
            return;
        }

        const data = {
            report_type: selected_report_type.toString(),
            description: report_description,
        };
        const url = "/json/messages/" + encodeURIComponent(message.id) + "/report";

        void channel.post({
            url,
            data,
            cache: false,
            success() {
                dialog_widget.close();
            },
            error(xhr) {
                ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                dialog_widget.hide_dialog_spinner();
            },
        });
    }

    dialog_widget.launch({
        html_heading: $t_html({
            defaultMessage: "Report a message",
        }),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Submit"}),
        help_link: "/help/report-a-message",
        id: "message_report_modal",
        form_id: "message_report_form",
        on_click: report_message,
        post_render: message_report_post_render,
        loading_spinner: true,
    });
}

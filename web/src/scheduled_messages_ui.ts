import $ from "jquery";
import assert from "minimalistic-assert";

import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";

import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import {$t} from "./i18n.ts";
import * as message_view from "./message_view.ts";
import * as people from "./people.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import type {ScheduledMessage} from "./scheduled_messages.ts";
import * as timerender from "./timerender.ts";

type ScheduledMessageComposeArgs =
    | {
          message_type: "stream";
          stream_id: number;
          topic: string;
          content: string;
      }
    | {
          message_type: "private";
          private_message_recipient: string;
          content: string;
          keep_composebox_empty: boolean;
      };

export function hide_scheduled_message_success_compose_banner(scheduled_message_id: number): void {
    $(
        `.message_scheduled_success_compose_banner[data-scheduled-message-id=${scheduled_message_id}]`,
    ).hide();
}

function narrow_via_edit_scheduled_message(compose_args: ScheduledMessageComposeArgs): void {
    if (compose_args.message_type === "stream") {
        message_view.show(
            [
                {
                    operator: "channel",
                    operand: compose_args.stream_id.toString(),
                },
                {operator: "topic", operand: compose_args.topic},
            ],
            {trigger: "edit scheduled message"},
        );
    } else {
        message_view.show([{operator: "dm", operand: compose_args.private_message_recipient}], {
            trigger: "edit scheduled message",
        });
    }
}

export function open_scheduled_message_in_compose(
    scheduled_message: ScheduledMessage,
    should_narrow_to_recipient?: boolean,
): void {
    let compose_args;
    let narrow_args;

    if (scheduled_message.type === "stream") {
        compose_args = {
            message_type: "stream" as const,
            stream_id: scheduled_message.to,
            topic: scheduled_message.topic,
            content: scheduled_message.content,
        };
        narrow_args = compose_args;
    } else {
        const recipient_ids = scheduled_message.to.filter(
            (recipient_id) => !people.get_by_user_id(recipient_id).is_inaccessible_user,
        );
        const recipient_emails = recipient_ids.map(
            (recipient_id) => people.get_by_user_id(recipient_id).email,
        );
        compose_args = {
            message_type: "private" as const,
            private_message_recipient_ids: recipient_ids,
            content: scheduled_message.content,
            keep_composebox_empty: true,
        };
        // Narrow filters still use emails for PMs, though we'll
        // eventually want to migrate that as well.
        narrow_args = {
            message_type: "private" as const,
            private_message_recipient: recipient_emails.join(","),
            content: scheduled_message.content,
            keep_composebox_empty: true,
        };
    }

    if (should_narrow_to_recipient) {
        narrow_via_edit_scheduled_message(narrow_args);
    }

    compose_actions.start(compose_args);
    scheduled_messages.set_selected_schedule_timestamp(
        scheduled_message.scheduled_delivery_timestamp,
    );
}

function show_message_unscheduled_banner(scheduled_delivery_timestamp: number): void {
    const deliver_at = timerender.get_full_datetime(
        new Date(scheduled_delivery_timestamp * 1000),
        "time",
    );
    const unscheduled_banner_html = render_compose_banner({
        banner_type: compose_banner.WARNING,
        banner_text: $t({
            defaultMessage: "This message is no longer scheduled to be sent.",
        }),
        button_text: $t({defaultMessage: "Schedule for {deliver_at}"}, {deliver_at}),
        classname: compose_banner.CLASSNAMES.unscheduled_message,
    });
    compose_banner.append_compose_banner_to_banner_list(
        $(unscheduled_banner_html),
        $("#compose_banners"),
    );
}

export function edit_scheduled_message(
    scheduled_message_id: number,
    should_narrow_to_recipient = true,
): void {
    const scheduled_message = scheduled_messages.scheduled_messages_by_id.get(scheduled_message_id);
    assert(scheduled_message !== undefined);

    scheduled_messages.delete_scheduled_message(scheduled_message_id, () => {
        open_scheduled_message_in_compose(scheduled_message, should_narrow_to_recipient);
        show_message_unscheduled_banner(scheduled_message.scheduled_delivery_timestamp);
    });
}

export function initialize(): void {
    $("body").on("click", ".undo_scheduled_message", (e) => {
        const scheduled_message_id = Number.parseInt(
            $(e.target)
                .parents(".message_scheduled_success_compose_banner")
                .attr("data-scheduled-message-id")!,
            10,
        );
        const should_narrow_to_recipient = false;
        edit_scheduled_message(scheduled_message_id, should_narrow_to_recipient);
        e.preventDefault();
        e.stopPropagation();
    });
}

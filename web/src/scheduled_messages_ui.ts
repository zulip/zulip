import {$} from "jquery";
import assert from "minimalistic-assert";

import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_split_messages from "./compose_split_messages.ts";
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
          private_message_recipient_ids: number[];
          content: string;
          keep_composebox_empty: boolean;
      };

export function hide_scheduled_message_success_compose_banner(scheduled_message_id: number): void {
    $(
        `.message_scheduled_success_compose_banner[data-scheduled-message-id=${scheduled_message_id}]`,
    ).hide();
    for (const banner of $(
        ".message_scheduled_success_compose_banner[data-scheduled-message-ids]",
    )) {
        const $banner = $(banner);
        const ids = $banner
            .attr("data-scheduled-message-ids")!
            .split(",")
            .map((id) => Number.parseInt(id, 10));
        if (ids.includes(scheduled_message_id)) {
            $banner.hide();
        }
    }
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
        const user_ids = compose_args.private_message_recipient_ids;
        message_view.show([{operator: "dm", operand: user_ids}], {
            trigger: "edit scheduled message",
        });
    }
}

export function open_scheduled_message_in_compose(
    scheduled_message: ScheduledMessage,
    should_narrow_to_recipient?: boolean,
): void {
    let compose_args;

    if (scheduled_message.type === "stream") {
        compose_args = {
            message_type: "stream" as const,
            stream_id: scheduled_message.to,
            topic: scheduled_message.topic,
            content: scheduled_message.content,
        };
    } else {
        const recipient_ids = scheduled_message.to.filter(
            (recipient_id) => !people.get_by_user_id(recipient_id).is_inaccessible_user,
        );
        compose_args = {
            message_type: "private" as const,
            private_message_recipient_ids: recipient_ids,
            content: scheduled_message.content,
            keep_composebox_empty: true,
        };
    }

    if (should_narrow_to_recipient) {
        narrow_via_edit_scheduled_message(compose_args);
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
    compose_banner.show_warning_message(
        $t({
            defaultMessage: "This message is no longer scheduled to be sent.",
        }),
        compose_banner.CLASSNAMES.unscheduled_message,
        $("#compose_banners"),
        {button_text: $t({defaultMessage: "Schedule for {deliver_at}"}, {deliver_at})},
    );
}

function restore_unscheduled_split_parts(parts: ScheduledMessage[], count: number): void {
    if (count === 0) {
        return;
    }
    const first_part = parts[0];
    assert(first_part !== undefined);
    const content = parts
        .slice(0, count)
        .map((part) => part.content)
        .join(compose_split_messages.SPLIT_DELIMITER);
    open_scheduled_message_in_compose({...first_part, content}, false);
    compose_split_messages.set_split_messages_enabled(true);
    compose_banner.update_split_messages_info_banner();
}

export function undo_split_scheduled_messages(
    scheduled_message_ids: number[],
    on_nothing_unscheduled?: () => void,
): void {
    const parts = scheduled_message_ids
        .map((scheduled_message_id) =>
            scheduled_messages.scheduled_messages_by_id.get(scheduled_message_id),
        )
        .filter((part) => part !== undefined);

    const first_part = parts[0];
    if (parts.length !== scheduled_message_ids.length || first_part === undefined) {
        compose_banner.show_partial_undo_failure(scheduled_message_ids.length);
        on_nothing_unscheduled?.();
        return;
    }

    const delete_part = (index: number): void => {
        if (index === parts.length) {
            restore_unscheduled_split_parts(parts, parts.length);
            show_message_unscheduled_banner(first_part.scheduled_delivery_timestamp);
            return;
        }
        const part = parts[index];
        assert(part !== undefined);
        scheduled_messages.delete_scheduled_message(
            part.scheduled_message_id,
            () => {
                delete_part(index + 1);
            },
            () => {
                restore_unscheduled_split_parts(parts, index);
                compose_banner.show_partial_undo_failure(parts.length - index);
                if (index === 0) {
                    on_nothing_unscheduled?.();
                }
            },
        );
    };
    delete_part(0);
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

    $("body").on("click", ".undo_split_scheduled_messages", (e) => {
        const $button = $(e.target);
        const scheduled_message_ids = $button
            .parents(".message_scheduled_success_compose_banner")
            .attr("data-scheduled-message-ids")!
            .split(",")
            .map((scheduled_message_id) => Number.parseInt(scheduled_message_id, 10));
        $button.prop("disabled", true);
        undo_split_scheduled_messages(scheduled_message_ids, () => {
            $button.prop("disabled", false);
        });
        e.preventDefault();
        e.stopPropagation();
    });
}

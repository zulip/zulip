import $ from "jquery";

import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t, $t_html} from "./i18n.ts";

type RankedSlot = {
    slot_id: number;
    start_time: string;
    end_time: string | null;
    available_count: number;
};

function format_slot(slot: RankedSlot): string {
    const start = new Date(slot.start_time);
    const end = slot.end_time ? new Date(slot.end_time) : null;

    const day = start.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
    });
    const start_time = start.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
    });
    const end_time = end
        ? end.toLocaleTimeString("en-US", {hour: "numeric", minute: "2-digit"})
        : undefined;
    const time_range = end_time ? `${start_time} - ${end_time}` : start_time;
    return `${day}, ${time_range}`;
}

function render_slot_picker(slots: RankedSlot[]): string {
    if (slots.length === 0) {
        return `<div class="availability-confirm-empty">${$t({
            defaultMessage: "No responses have been submitted yet.",
        })}</div>`;
    }

    const options = slots
        .map(
            (slot, index) => `<label class="meeting-confirm-option" style="display:block; margin: 8px 0;">
            <input type="radio" name="winning_slot_id" value="${slot.slot_id}" ${index === 0 ? "checked" : ""} />
            <span style="margin-left: 6px;">${format_slot(slot)} (${slot.available_count} available)</span>
        </label>`,
        )
        .join("");

    return `<div class="meeting-confirm-options">${options}</div>`;
}

export function open(meeting_id: number, on_confirmed?: () => void): void {
    void channel.get({
        url: `/json/meetings/${meeting_id}/responses`,
        success(data) {
            const slots = (data as {slots: RankedSlot[]}).slots;
            dialog_widget.launch({
                modal_title_html: $t_html({defaultMessage: "Choose final meeting time"}),
                modal_content_html: render_slot_picker(slots),
                modal_submit_button_text: $t({defaultMessage: "Confirm slot"}),
                id: "meeting-confirm-modal",
                form_id: "meeting-confirm-form",
                on_click() {
                    const selected = Number(
                        $<HTMLInputElement>("input[name='winning_slot_id']:checked").val(),
                    );
                    if (!selected) {
                        return;
                    }

                    void channel.post({
                        url: `/json/meetings/${meeting_id}/confirm`,
                        data: {winning_slot_id: JSON.stringify(selected)},
                        success() {
                            if (on_confirmed) {
                                on_confirmed();
                            }
                        },
                    });
                },
            });
        },
    });
}

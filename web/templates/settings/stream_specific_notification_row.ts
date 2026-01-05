import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_stream_privacy from "../stream_privacy.ts";
import render_notification_settings_checkboxes from "./notification_settings_checkboxes.ts";

export default function render_stream_specific_notification_row(context) {
    const out = html`<tr
        class="stream-notifications-row"
        data-stream-id="${context.stream.stream_id}"
    >
        <td class="stream-controls">
            <span
                class="stream-privacy-original-color-${context.stream
                    .stream_id} stream-privacy filter-icon"
                style="color: ${context.stream.color}"
            >
                ${{
                    __html: render_stream_privacy({
                        is_web_public: context.stream.is_web_public,
                        invite_only: context.stream.invite_only,
                    }),
                }}
            </span>
            ${context.stream.stream_name}
            <i
                class="zulip-icon icon-button-brand zulip-icon-mute tippy-zulip-delayed-tooltip unmute_stream"
                role="button"
                tabindex="0"
                data-tippy-content="${$t({defaultMessage: "Unmute"})}"
                aria-label="${$t({defaultMessage: "Unmute"})}"
                ${!to_bool(context.muted) ? html`style="display: none;"` : ""}
            ></i>
            <i
                class="zulip-icon icon-button-neutral zulip-icon-reset tippy-zulip-delayed-tooltip reset_stream_notifications"
                role="button"
                tabindex="0"
                data-tippy-content="${$t({defaultMessage: "Reset to default notifications"})}"
                aria-label="${$t({defaultMessage: "Reset to default notifications"})}"
            ></i>
        </td>
        ${to_array(context.stream_specific_notification_settings).map(
            (setting) =>
                html` ${{
                    __html: render_notification_settings_checkboxes({
                        push_notifications_disabled: context.push_notifications_disabled,
                        is_mobile_checkbox: setting === "push_notifications",
                        is_disabled: context.is_disabled?.[setting],
                        is_checked: context.stream?.[setting],
                        prefix: context.stream?.stream_id,
                        setting_name: setting,
                    }),
                }}`,
        )}
    </tr> `;
    return to_html(out);
}

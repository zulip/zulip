import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import {postprocess_content} from "../src/postprocess_content.ts";
import render_icon_button from "./components/icon_button.ts";
import render_scheduled_message_stream_pm_common from "./scheduled_message_stream_pm_common.ts";

export default function render_reminder_list(context) {
    const out = to_array(context.reminders_data).map(
        (reminder) => html`
            <div
                class="reminder-row overlay-message-row"
                data-reminder-id="${reminder.reminder_id}"
            >
                <div class="reminder-info-box overlay-message-info-box" tabindex="0">
                    <div
                        class="message_header message_header_private_message overlay-message-header"
                    >
                        <div class="message-header-contents">
                            <div class="message_label_clickable stream_label">
                                <span class="private_message_header_icon"
                                    ><i class="zulip-icon zulip-icon-user"></i
                                ></span>
                                <span class="private_message_header_name"
                                    >${$t({defaultMessage: "Notification Bot to you"})}</span
                                >
                            </div>
                            ${{__html: render_scheduled_message_stream_pm_common(reminder)}}
                        </div>
                    </div>
                    <div
                        class="message_row${!to_bool(reminder.is_stream) ? " private-message" : ""}"
                        role="listitem"
                    >
                        <div class="messagebox">
                            <div class="messagebox-content">
                                <div class="message_top_line">
                                    <div class="overlay_message_controls">
                                        ${{
                                            __html: render_icon_button({
                                                ["aria-label"]: $t({defaultMessage: "Delete"}),
                                                ["data-tooltip-template-id"]:
                                                    "delete-reminder-tooltip-template",
                                                icon: "trash",
                                                custom_classes:
                                                    "delete-overlay-message tippy-zulip-delayed-tooltip",
                                                intent: "danger",
                                            }),
                                        }}
                                    </div>
                                </div>
                                <div
                                    class="message_content rendered_markdown restore-overlay-message"
                                >
                                    ${{__html: postprocess_content(reminder.rendered_content)}}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `,
    );
    return to_html(out);
}

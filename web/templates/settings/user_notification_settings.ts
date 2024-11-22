import {html, to_html} from "../../shared/src/html.ts";
import render_notification_settings from "./notification_settings.ts";

export default function render_user_notification_settings(context) {
    const out = html`<div
        id="user-notification-settings"
        class="settings-section"
        data-name="notifications"
    >
        ${{
            __html: render_notification_settings({
                for_realm_settings: false,
                prefix: "user_",
                ...context,
            }),
        }}
    </div> `;
    return to_html(out);
}

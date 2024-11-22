import {html, to_html} from "../shared/src/html.ts";
import render_account_settings from "./settings/account_settings.ts";
import render_alert_word_settings from "./settings/alert_word_settings.ts";
import render_attachments_settings from "./settings/attachments_settings.ts";
import render_bot_settings from "./settings/bot_settings.ts";
import render_muted_users_settings from "./settings/muted_users_settings.ts";
import render_profile_settings from "./settings/profile_settings.ts";
import render_user_notification_settings from "./settings/user_notification_settings.ts";
import render_user_preferences from "./settings/user_preferences.ts";
import render_user_topics_settings from "./settings/user_topics_settings.ts";

export default function render_settings_tab(context) {
    const out = html`<div id="settings-change-box">
        ${{__html: render_profile_settings(context)}} ${{__html: render_account_settings(context)}}
        ${{__html: render_user_preferences(context)}}
        ${{__html: render_user_notification_settings(context)}}
        ${{__html: render_bot_settings(context)}} ${{__html: render_alert_word_settings()}}
        ${{__html: render_attachments_settings()}} ${{__html: render_user_topics_settings()}}
        ${{__html: render_muted_users_settings()}}
    </div> `;
    return to_html(out);
}

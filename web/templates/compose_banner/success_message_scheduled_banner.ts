import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_success_message_scheduled_banner(context) {
    const out = html`<div
        class="main-view-banner success message_scheduled_success_compose_banner"
        data-scheduled-message-id="${context.scheduled_message_id}"
    >
        <div class="main-view-banner-elements-wrapper">
            <p class="banner_content">
                ${$t(
                    {defaultMessage: "Your message has been scheduled for {deliver_at}."},
                    {deliver_at: context.deliver_at},
                )}
                <a href="#scheduled">${$t({defaultMessage: "View scheduled messages"})}</a>
            </p>
            <button class="main-view-banner-action-button undo_scheduled_message">
                ${$t({defaultMessage: "Undo"})}
            </button>
        </div>
        <a role="button" class="zulip-icon zulip-icon-close main-view-banner-close-button"></a>
    </div> `;
    return to_html(out);
}

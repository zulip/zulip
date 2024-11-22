import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_mark_as_read_only_in_conversation_view() {
    const out = html`<div
        id="mark_as_read_turned_off_banner"
        class="main-view-banner home-error-bar info"
    >
        <p id="mark_as_read_turned_off_content" class="banner_content">
            ${$html_t(
                {
                    defaultMessage:
                        "Messages will not be automatically marked as read because this is not a <z-conversation-view>conversation</z-conversation-view> view. <z-link>Change setting</z-link>",
                },
                {
                    ["z-conversation-view"]: (content) =>
                        html`<a href="/help/reading-conversations">${content}</a>`,
                    ["z-link"]: (content) => html`<a href="/#settings/preferences">${content}</a>`,
                },
            )}
        </p>
        <button id="mark_view_read" class="main-view-banner-action-button">
            ${$t({defaultMessage: "Mark as read"})}
        </button>
        <a
            role="button"
            id="mark_as_read_close"
            class="zulip-icon zulip-icon-close main-view-banner-close-button"
        ></a>
    </div> `;
    return to_html(out);
}

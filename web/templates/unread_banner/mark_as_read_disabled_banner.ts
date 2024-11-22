import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_mark_as_read_disabled_banner() {
    const out = html`<div
        id="mark_as_read_turned_off_banner"
        class="main-view-banner home-error-bar info"
    >
        <p id="mark_as_read_turned_off_content" class="banner_content">
            ${$html_t(
                {
                    defaultMessage:
                        "Messages will not be automatically marked as read. <z-link>Change setting</z-link>",
                },
                {["z-link"]: (content) => html`<a href="/#settings/preferences">${content}</a>`},
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

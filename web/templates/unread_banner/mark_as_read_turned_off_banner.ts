import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_mark_as_read_turned_off_banner() {
    const out = html`<div
        id="mark_as_read_turned_off_banner"
        class="main-view-banner home-error-bar info"
    >
        <p id="mark_as_read_turned_off_content" class="banner_content">
            ${$t({
                defaultMessage:
                    "To preserve your reading state, this view does not mark messages as read.",
            })}
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

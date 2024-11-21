import {html, to_html} from "../../src/html.ts";

export default function render_guest_in_dm_recipient_warning(context) {
    const out = html`<div
        class="above_compose_banner main-view-banner warning-style ${context.classname}"
    >
        <p class="banner_content">${context.banner_text}</p>
        <a role="button" class="zulip-icon zulip-icon-close main-view-banner-close-button"></a>
    </div> `;
    return to_html(out);
}

import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_login_to_view_image_button() {
    const out = html`<div class="spectator_login_for_image_button">
        <a class="login_button color_animated_button" href="/login/">
            <i class="zulip-icon zulip-icon-log-in"></i>
            <span class="color-animated-button-text"
                >${$t({defaultMessage: "Log in to view image"})}</span
            >
        </a>
    </div> `;
    return to_html(out);
}

import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_copy_invite_link(context) {
    const out = html`<div id="copy_generated_link_container">
        <span>${$t({defaultMessage: "Link:"})}</span>
        <a href="${context.invite_link}" id="multiuse_invite_link">${context.invite_link}</a>

        <span
            id="copy_generated_invite_link"
            class="copy-button"
            data-tippy-content="${$t({defaultMessage: "Copy link"})}"
            data-tippy-placement="top"
            aria-label="${$t({defaultMessage: "Copy link"})}"
            data-clipboard-text="${context.invite_link}"
            role="button"
        >
            <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>
        </span>
    </div> `;
    return to_html(out);
}

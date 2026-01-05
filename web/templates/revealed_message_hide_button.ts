import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_revealed_message_hide_button(context) {
    const out = html`${to_bool(context.is_inline_hide_button)
            ? html` <span class="inline-hide-button-space-wrapper"> </span> `
            : ""}<button
            data-message-id="${context.message_id}"
            class="action-button rehide-muted-user-message ${to_bool(context.is_inline_hide_button)
                ? "inline-hide-button"
                : "block-hide-button"}"
            tabindex="0"
            aria-label="${$t({defaultMessage: "Hide message from muted user"})}"
        >
            <i class="zulip-icon zulip-icon-hide"></i>
            <span class="action-button-label">${$t({defaultMessage: "Hide"})}</span>
        </button> `;
    return to_html(out);
}

import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_filter_text_input(context) {
    const out = html`<div class="search-container">
        <input
            type="text"
            ${to_bool(context.id) ? html`id="${context.id}"` : ""}
            class="search filter_text_input"
            placeholder="${context.placeholder}"
            aria-label="${context.aria_label}"
        />
        <button type="button" class="clear-filter">
            <i class="zulip-icon zulip-icon-close"></i>
        </button>
    </div> `;
    return to_html(out);
}

import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_section_header(context) {
    const out = html`<i
            class="buddy-list-section-toggle zulip-icon zulip-icon-heading-triangle-right ${to_bool(
                context.is_collapsed,
            )
                ? "rotate-icon-right"
                : "rotate-icon-down"}"
            aria-hidden="true"
        ></i>
        <h5
            id="${context.id}"
            data-user-count="${context.user_count}"
            class="buddy-list-heading no-style hidden-for-spectators"
        >
            ${context.header_text} (<span class="buddy-list-heading-user-count"
                >${context.user_count}</span
            >)
        </h5> `;
    return to_html(out);
}

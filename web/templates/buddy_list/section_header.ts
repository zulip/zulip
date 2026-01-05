import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_section_header(context) {
    const out = html`<i
            class="buddy-list-section-toggle zulip-icon zulip-icon-heading-triangle-right ${to_bool(
                context.is_collapsed,
            )
                ? "rotate-icon-right"
                : "rotate-icon-down"}"
            aria-hidden="true"
        ></i>
        <h5 id="${context.id}" class="buddy-list-heading no-style hidden-for-spectators">
            <span class="buddy-list-heading-text">${context.header_text}</span>
            ${/* Hide the count until we have fetched data to display the correct count */ ""}
            <span class="buddy-list-heading-user-count-with-parens hide">
                (<span class="buddy-list-heading-user-count"></span>)
            </span>
        </h5> `;
    return to_html(out);
}

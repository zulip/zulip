import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_subscriber_count(context) {
    const out = html`<i class="fa fa-user-o" aria-hidden="true"></i> ${to_bool(
            context.can_access_subscribers,
        )
            ? html`<span class="subscriber-count-text"
                  >${context.subscriber_count.toLocaleString()}</span
              > `
            : html`<i class="subscriber-count-lock fa fa-lock" aria-hidden="true"></i> `}`;
    return to_html(out);
}

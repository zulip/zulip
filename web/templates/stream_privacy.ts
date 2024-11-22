import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_stream_privacy(context) {
    const out =
        /* This controls whether the swatch next to streams in the left sidebar has a lock icon. */ to_bool(
            context.invite_only,
        )
            ? html`<i class="zulip-icon zulip-icon-lock" aria-hidden="true"></i> `
            : to_bool(context.is_web_public)
              ? html`<i class="zulip-icon zulip-icon-globe" aria-hidden="true"></i> `
              : html`<i class="zulip-icon zulip-icon-hashtag" aria-hidden="true"></i> `;
    return to_html(out);
}

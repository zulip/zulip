import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_stream_privacy_icon(context) {
    const out =
        /* This controls whether the swatch next to streams in the stream edit page has a lock icon. */ to_bool(
            context.invite_only,
        )
            ? html`<div class="large-icon" ${to_bool(context.title_icon_color) ? html`style="color: ${context.title_icon_color}` : ""}">
    <i class="zulip-icon zulip-icon-lock" aria-hidden="true"></i>
</div>
`
            : to_bool(context.is_web_public)
              ? html`<div class="large-icon" ${to_bool(context.title_icon_color) ? html`style="color: ${context.title_icon_color}` : ""}">
    <i class="zulip-icon zulip-icon-globe" aria-hidden="true"></i>
</div>
`
              : html`<div class="large-icon" ${to_bool(context.title_icon_color) ? html`style="color: ${context.title_icon_color}` : ""}">
    <i class="zulip-icon zulip-icon-hashtag" aria-hidden="true"></i>
</div>
`;
    return to_html(out);
}

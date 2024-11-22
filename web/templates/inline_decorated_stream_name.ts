import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_inline_decorated_stream_name(context) {
    const out =
        /* This controls whether the swatch next to streams in the left sidebar has a lock icon. */ to_bool(
            context.stream.invite_only,
        )
            ? html`<i
                      class="zulip-icon zulip-icon-lock stream-privacy-type-icon"
                      ${to_bool(context.show_colored_icon)
                          ? html`style="color: ${context.stream.color}"`
                          : ""}
                      aria-hidden="true"
                  ></i>
                  ${context.stream.name}`
            : to_bool(context.stream.is_web_public)
              ? html`<i
                        class="zulip-icon zulip-icon-globe stream-privacy-type-icon"
                        ${to_bool(context.show_colored_icon)
                            ? html`style="color: ${context.stream.color}"`
                            : ""}
                        aria-hidden="true"
                    ></i>
                    ${context.stream.name}`
              : html`<i
                        class="zulip-icon zulip-icon-hashtag stream-privacy-type-icon"
                        ${to_bool(context.show_colored_icon)
                            ? html`style="color: ${context.stream.color}"`
                            : ""}
                        aria-hidden="true"
                    ></i>
                    ${context.stream.name}`;
    return to_html(out);
}

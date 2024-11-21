import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_inline_decorated_channel_name(context) {
    const out =
        /* This controls whether the swatch next to streams in the left sidebar has a lock icon. */ to_bool(
            context.stream.is_archived,
        )
            ? html`<i
                      class="zulip-icon zulip-icon-archive channel-privacy-type-icon"
                      ${to_bool(context.show_colored_icon)
                          ? html`style="color: ${context.stream.color}"`
                          : ""}
                      aria-hidden="true"
                  ></i>
                  <span class="decorated-channel-name">${context.stream.name}</span>`
            : to_bool(context.stream.invite_only)
              ? html`<i
                        class="zulip-icon zulip-icon-lock channel-privacy-type-icon"
                        ${to_bool(context.show_colored_icon)
                            ? html`style="color: ${context.stream.color}"`
                            : ""}
                        aria-hidden="true"
                    ></i>
                    <span class="decorated-channel-name">${context.stream.name}</span>`
              : to_bool(context.stream.is_web_public)
                ? html`<i
                          class="zulip-icon zulip-icon-globe channel-privacy-type-icon"
                          ${to_bool(context.show_colored_icon)
                              ? html`style="color: ${context.stream.color}"`
                              : ""}
                          aria-hidden="true"
                      ></i>
                      <span class="decorated-channel-name">${context.stream.name}</span>`
                : html`<i
                          class="zulip-icon zulip-icon-hashtag channel-privacy-type-icon"
                          ${to_bool(context.show_colored_icon)
                              ? html`style="color: ${context.stream.color}"`
                              : ""}
                          aria-hidden="true"
                      ></i>
                      <span class="decorated-channel-name">${context.stream.name}</span>`;
    return to_html(out);
}

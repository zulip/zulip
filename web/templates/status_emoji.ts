import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_status_emoji(context) {
    const out = to_bool(context)
        ? to_bool(context.emoji_alt_code)
            ? html`<span class="emoji_alt_code">&nbsp;:${context.emoji_name}:</span>`
            : to_bool(context.still_url)
              ? html`<img
                    src="${context.still_url}"
                    class="emoji status-emoji status-emoji-name"
                    data-animated-url="${context.url}"
                    data-still-url="${context.still_url}"
                    data-tippy-content=":${context.emoji_name}:"
                />`
              : to_bool(context.url)
                ? /* note that we have no still_url */ html`<img
                      src="${context.url}"
                      class="emoji status-emoji status-emoji-name"
                      data-animated-url="${context.url}"
                      data-tippy-content=":${context.emoji_name}:"
                  />`
                : to_bool(context.emoji_name)
                  ? html`<span
                        class="emoji status-emoji status-emoji-name emoji-${context.emoji_code}"
                        data-tippy-content=":${context.emoji_name}:"
                    ></span>`
                  : ""
        : "";
    return to_html(out);
}

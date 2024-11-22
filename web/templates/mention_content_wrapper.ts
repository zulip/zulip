import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_mention_content_wrapper(context) {
    const out = html`<span class="mention-content-wrapper">${context.mention_text}</span>${to_bool(
            context.is_bot,
        )
            ? html`<i
                  class="zulip-icon zulip-icon-bot"
                  aria-label="${$t({defaultMessage: "Bot"})}"
              ></i>`
            : ""}`;
    return to_html(out);
}

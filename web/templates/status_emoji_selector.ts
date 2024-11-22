import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_status_emoji_selector(context) {
    const out = to_bool(context.selected_emoji)
        ? to_bool(context.selected_emoji.emoji_alt_code)
            ? html` <div class="emoji_alt_code">&nbsp;:${context.selected_emoji.emoji_name}:</div> `
            : to_bool(context.selected_emoji.url)
              ? html` <img src="${context.selected_emoji.url}" class="emoji selected-emoji" /> `
              : html`
                    <div
                        class="emoji selected-emoji emoji-${context.selected_emoji.emoji_code}"
                    ></div>
                `
        : html` <a type="button" class="smiley-icon show zulip-icon zulip-icon-smile"></a> `;
    return to_html(out);
}

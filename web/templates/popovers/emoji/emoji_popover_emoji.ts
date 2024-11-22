import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";

export default function render_emoji_popover_emoji(context) {
    const out = ((emoji_dict) =>
        html`<div
            class="emoji-popover-emoji ${to_bool(emoji_dict.has_reacted) ? "reacted" : ""}"
            data-emoji-name="${to_bool(emoji_dict.emoji_name)
                ? emoji_dict.emoji_name
                : emoji_dict.name}"
            tabindex="0"
            data-emoji-id="${context.type},${context.section},${context.index}"
        >
            ${to_bool(emoji_dict.is_realm_emoji)
                ? html` <img src="${emoji_dict.url}" class="emoji" /> `
                : html` <div class="emoji emoji-${emoji_dict.emoji_code}"></div> `}
        </div> `)(context.emoji_dict);
    return to_html(out);
}

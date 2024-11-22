import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";

export default function render_emoji_showcase(context) {
    const out = ((emoji_dict) =>
        html`<div class="emoji-showcase">
            ${to_bool(emoji_dict.is_realm_emoji)
                ? html` <img src="${emoji_dict.url}" class="emoji emoji-preview" /> `
                : html` <div class="emoji emoji-preview emoji-${emoji_dict.emoji_code}"></div> `}
            <div class="emoji-canonical-name" title="${emoji_dict.name}">${emoji_dict.name}</div>
        </div> `)(context.emoji_dict);
    return to_html(out);
}

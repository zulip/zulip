import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_message_reaction(context) {
    const out = html`<div
        class="message_reaction_container ${to_bool(context.is_archived) ? "disabled" : ""}"
    >
        <div
            class="${context.class} ${to_bool(context.is_archived) ? "disabled" : ""}"
            aria-label="${context.label}"
            data-reaction-id="${context.local_id}"
        >
            ${to_bool(context.emoji_alt_code)
                ? html` <div class="emoji_alt_code">&nbsp;:${context.emoji_name}:</div> `
                : to_bool(context.is_realm_emoji)
                  ? html` <img src="${context.url}" class="emoji" /> `
                  : html` <div class="emoji emoji-${context.emoji_code}"></div> `}
            <div class="message_reaction_count">${context.vote_text}</div>
        </div>
    </div> `;
    return to_html(out);
}

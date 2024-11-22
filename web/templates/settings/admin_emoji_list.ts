import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_admin_emoji_list(context) {
    const out = ((emoji) =>
        html`<tr class="emoji_row" id="emoji_${emoji.name}">
            <td>
                <span class="emoji_name">${emoji.display_name}</span>
            </td>
            <td>
                <span class="emoji_image">
                    <a href="${emoji.source_url}" target="_blank" rel="noopener noreferrer">
                        <img class="emoji" src="${emoji.source_url}" alt="${emoji.display_name}" />
                    </a>
                </span>
            </td>
            <td>
                ${to_bool(emoji.author)
                    ? ((author) => html`
                          <span class="emoji_author panel_user_list"
                              >${{
                                  __html: render_user_display_only_pill({
                                      img_src: author.avatar_url,
                                      display_value: author.full_name,
                                      ...author,
                                  }),
                              }}</span
                          >
                      `)(emoji.author)
                    : html`
                          <span class="emoji_author"
                              >${$t({defaultMessage: "Unknown author"})}</span
                          >
                      `}
            </td>
            <td>
                <button
                    class="button rounded small delete button-danger tippy-zulip-delayed-tooltip"
                    ${!to_bool(emoji.can_delete_emoji) ? html`disabled="disabled"` : ""}
                    data-tippy-content="${$t({defaultMessage: "Delete"})}"
                    data-emoji-name="${emoji.name}"
                >
                    <i class="fa fa-trash-o" aria-hidden="true"></i>
                </button>
            </td>
        </tr> `)(context.emoji);
    return to_html(out);
}

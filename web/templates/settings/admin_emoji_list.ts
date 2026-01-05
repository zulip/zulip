import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_admin_emoji_list(context) {
    const out = ((emoji) =>
        html`<tr class="emoji_row" id="emoji_${emoji.name}" data-emoji-name="${emoji.name}">
            <td>
                <span class="emoji_name">${emoji.display_name}</span>
                ${to_bool(emoji.is_overriding_default)
                    ? html`
                          <i
                              class="zulip-icon zulip-icon-exclamation-circle tippy-zulip-tooltip emoji-override-warning"
                              data-tippy-content="${$t({
                                  defaultMessage:
                                      "This custom emoji overrides a default emoji with the same name.",
                              })}"
                          ></i>
                      `
                    : ""}
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
                ${{
                    __html: render_icon_button({
                        ["data-tippy-content"]: $t({defaultMessage: "Deactivate"}),
                        disabled: !to_bool(emoji.can_delete_emoji),
                        custom_classes: "tippy-zulip-delayed-tooltip delete",
                        intent: "danger",
                        icon: "trash",
                    }),
                }}
            </td>
        </tr> `)(context.emoji);
    return to_html(out);
}

import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_user_group_list_item(context) {
    const out = html`<tr data-group-id="${context.group_id}">
        <td class="group_list_item">
            ${to_bool(context.is_guest)
                ? html` ${context.name} `
                : html`
                      <a class="group_list_item_link" href="${context.group_edit_url}"
                          >${context.name}</a
                      >
                  `}
        </td>
    </tr> `;
    return to_html(out);
}

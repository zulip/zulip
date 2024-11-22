import {html, to_html} from "../shared/src/html.ts";

export default function render_empty_list_widget_for_table(context) {
    const out = html`<tr>
        <td class="empty-table-message" colspan="${context.column_count}">
            ${context.empty_list_message}
        </td>
    </tr> `;
    return to_html(out);
}

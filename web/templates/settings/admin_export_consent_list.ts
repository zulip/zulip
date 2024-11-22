import {html, to_html} from "../../shared/src/html.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_admin_export_consent_list(context) {
    const out = ((export_consent) =>
        html`<tr>
            <td class="user_name panel_user_list">
                ${{
                    __html: render_user_display_only_pill({
                        is_active: true,
                        img_src: export_consent.img_src,
                        user_id: export_consent.user_id,
                        display_value: export_consent.full_name,
                    }),
                }}
            </td>
            <td>
                <span>${export_consent.consent}</span>
            </td>
        </tr> `)(context.export_consent);
    return to_html(out);
}

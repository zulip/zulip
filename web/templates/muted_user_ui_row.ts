import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_action_button from "./components/action_button.ts";

export default function render_muted_user_ui_row(context) {
    const out = ((muted_user) =>
        html`<tr
            data-user-id="${muted_user.user_id}"
            data-user-name="${muted_user.user_name}"
            data-date-muted="${muted_user.date_muted_str}"
        >
            <td>${muted_user.user_name}</td>
            <td>${muted_user.date_muted_str}</td>
            <td class="actions">
                ${to_bool(muted_user.can_unmute)
                    ? html` ${{
                          __html: render_action_button({
                              custom_classes: "settings-unmute-user",
                              intent: "danger",
                              attention: "quiet",
                              label: $t({defaultMessage: "Unmute"}),
                          }),
                      }}`
                    : ""}
            </td>
        </tr> `)(context.muted_user);
    return to_html(out);
}

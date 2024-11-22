import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_typing_notification from "./typing_notification.ts";

export default function render_typing_notifications(context) {
    const out = /* Typing notifications */ html`<ul id="typing_notification_list">
        ${to_bool(context.several_users)
            ? html`
                  <li class="typing_notification">
                      ${$t({defaultMessage: "Several people are typing…"})}
                  </li>
              `
            : to_array(context.users).map(
                  (user) => html` ${{__html: render_typing_notification(user)}}`,
              )}
    </ul> `;
    return to_html(out);
}

import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_admin_playground_list(context) {
    const out = ((playground) =>
        html`<tr class="playground_row" data-playground-id="${playground.id}">
            <td>
                <span class="playground_pygments_language">${playground.pygments_language}</span>
            </td>
            <td>
                <span class="playground_name">${playground.playground_name}</span>
            </td>
            <td>
                <span class="playground_url_template">${playground.url_template}</span>
            </td>
            ${to_bool(context.can_modify)
                ? html`
                      <td class="no-select actions">
                          ${{
                              __html: render_icon_button({
                                  ["aria-label"]: $t({defaultMessage: "Delete"}),
                                  ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                                  custom_classes: "delete-code-playground delete",
                                  intent: "danger",
                                  icon: "trash",
                              }),
                          }}
                      </td>
                  `
                : ""}
        </tr> `)(context.playground);
    return to_html(out);
}

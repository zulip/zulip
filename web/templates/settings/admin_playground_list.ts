import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_admin_playground_list(context) {
    const out = ((playground) =>
        html`<tr class="playground_row">
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
                          <button
                              class="button small delete button-danger tippy-zulip-tooltip"
                              data-playground-id="${playground.id}"
                              data-tippy-content="${$t({
                                  defaultMessage: "Delete",
                              })} ${playground.playground_name}"
                              aria-label="${$t({
                                  defaultMessage: "Delete",
                              })} ${playground.playground_name}"
                          >
                              <i class="fa fa-trash-o"></i>
                          </button>
                      </td>
                  `
                : ""}
        </tr> `)(context.playground);
    return to_html(out);
}

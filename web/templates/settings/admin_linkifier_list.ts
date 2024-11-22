import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_admin_linkifier_list(context) {
    const out = ((linkifier) =>
        html`<tr
            class="linkifier_row${to_bool(context.can_modify) && to_bool(context.can_drag)
                ? " movable-row"
                : ""}"
            data-linkifier-id="${linkifier.id}"
        >
            <td>
                ${to_bool(context.can_modify) && to_bool(context.can_drag)
                    ? html`
                          <span class="move-handle">
                              <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
                              <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
                          </span>
                      `
                    : ""} <span class="linkifier_pattern">${linkifier.pattern}</span>
            </td>
            <td>
                <span class="linkifier_url_template">${linkifier.url_template}</span>
            </td>
            ${to_bool(context.can_modify)
                ? html`
                      <td class="no-select actions">
                          <button
                              class="button small rounded edit button-warning tippy-zulip-delayed-tooltip"
                              data-linkifier-id="${linkifier.id}"
                              data-tippy-content="${$t({defaultMessage: "Edit"})}"
                              aria-label="${$t({defaultMessage: "Edit"})}"
                          >
                              <i class="fa fa-pencil"></i>
                          </button>
                          <button
                              class="button small rounded delete button-danger tippy-zulip-delayed-tooltip"
                              data-linkifier-id="${linkifier.id}"
                              data-tippy-content="${$t({defaultMessage: "Delete"})}"
                              aria-label="${$t({defaultMessage: "Delete"})}"
                          >
                              <i class="fa fa-trash-o"></i>
                          </button>
                      </td>
                  `
                : ""}
        </tr> `)(context.linkifier);
    return to_html(out);
}

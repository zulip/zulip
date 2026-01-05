import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

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
                          ${{
                              __html: render_icon_button({
                                  ["aria-label"]: $t({defaultMessage: "Edit"}),
                                  ["data-tippy-content"]: $t({defaultMessage: "Edit"}),
                                  custom_classes: "tippy-zulip-delayed-tooltip edit",
                                  intent: "neutral",
                                  icon: "edit",
                              }),
                          }}
                          ${{
                              __html: render_icon_button({
                                  ["aria-label"]: $t({defaultMessage: "Delete"}),
                                  ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                                  custom_classes: "tippy-zulip-delayed-tooltip delete",
                                  intent: "danger",
                                  icon: "trash",
                              }),
                          }}
                      </td>
                  `
                : ""}
        </tr> `)(context.linkifier);
    return to_html(out);
}

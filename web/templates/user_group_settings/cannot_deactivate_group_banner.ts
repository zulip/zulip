import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_cannot_deactivate_group_banner(context) {
    const out = html`<div class="cannot-deactivate-group-banner main-view-banner error">
        <p class="banner-text">
            ${to_bool(context.group_used_for_permissions)
                ? html`
                      ${$t({
                          defaultMessage:
                              "To deactivate this group, you must first remove all permissions assigned to it.",
                      })}
                  `
                : $html_t(
                      {
                          defaultMessage:
                              "To deactivate this group, you must first remove it from all other groups. This group is currently a subgroup of: <z-supergroup-names></z-supergroup-names>.",
                      },
                      {
                          ["z-supergroup-names"]: () =>
                              to_array(context.supergroups).map(
                                  (supergroup, supergroup_index, supergroup_array) =>
                                      html` <a
                                              class="view-group-members"
                                              data-group-id="${supergroup.group_id}"
                                              href="${supergroup.settings_url}"
                                              >${supergroup.group_name}</a
                                          >${supergroup_index !== supergroup_array.length - 1
                                              ? ", "
                                              : ""}`,
                              ),
                      },
                  )}
        </p>
        ${to_bool(context.group_used_for_permissions)
            ? html`
                  <button class="permissions-button main-view-banner-action-button">
                      ${$t({defaultMessage: "View permissions"})}
                  </button>
              `
            : ""}
    </div> `;
    return to_html(out);
}

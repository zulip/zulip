import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_user_group_membership_request_result(context) {
    const out = html`${to_bool(context.message)
        ? html`${context.message}
              <br /> `
        : ""}${to_bool(context.already_added_users)
        ? html`${to_array(context.already_added_users).map(
                  (user, user_index, user_array) =>
                      html`${user_index === 0
                              ? html` ${$t({defaultMessage: "Already members:"})} `
                              : ""}
                          <a data-user-id="${user.user_id}" class="view_user_profile"
                              >${user.full_name}</a
                          >${user_index !== user_array.length - 1 ? "," : "."} `,
              )} <br /> `
        : ""}${to_bool(context.ignored_deactivated_users)
        ? html`${to_array(context.ignored_deactivated_users).map(
                  (user, user_index, user_array) =>
                      html`${user_index === 0
                              ? html` ${$t({defaultMessage: "Ignored deactivated users:"})} `
                              : ""}
                          <a data-user-id="${user.user_id}" class="view_user_profile"
                              >${user.full_name}</a
                          >${user_index !== user_array.length - 1 ? "," : "."} `,
              )} <br /> `
        : ""}${to_bool(context.already_added_subgroups)
        ? html`${to_array(context.already_added_subgroups).map(
                  (subgroup, subgroup_index, subgroup_array) =>
                      html`${subgroup_index === 0
                              ? html` ${$t({defaultMessage: "Already subgroups:"})} `
                              : ""}
                          <a data-user-group-id="${subgroup.id}" class="view_user_group"
                              >${subgroup.name}</a
                          >${subgroup_index !== subgroup_array.length - 1 ? "," : "."} `,
              )} <br /> `
        : ""}${to_bool(context.ignored_deactivated_groups)
        ? to_array(context.ignored_deactivated_groups).map(
              (group, group_index, group_array) =>
                  html`${group_index === 0
                          ? html` ${$t({defaultMessage: "Ignored deactivated groups:"})} `
                          : ""}
                      <a data-user-group-id="${group.id}" class="view_user_group">${group.name}</a
                      >${group_index !== group_array.length - 1 ? "," : "."} `,
          )
        : ""}`;
    return to_html(out);
}

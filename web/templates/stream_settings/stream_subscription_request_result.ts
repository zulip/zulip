import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_stream_subscription_request_result(context) {
    const out = html`${to_bool(context.message)
        ? html`${context.message}
              <br /> `
        : ""}${to_bool(context.subscribed_users)
        ? html`${to_bool(context.subscribed_users[1])
                  ? html` ${$t({defaultMessage: "Successfully subscribed users:"})} `
                  : html` ${$t({defaultMessage: "Successfully subscribed user:"})} `}${to_array(
                  context.subscribed_users,
              ).map(
                  (user, user_index, user_array) => html`
                      <a data-user-id="${user.user_id}" class="view_user_profile"
                          >${user.full_name}</a
                      >${user_index !== user_array.length - 1 ? "," : "."}
                  `,
              )} <br /> `
        : ""}${to_bool(context.already_subscribed_users)
        ? html`${to_array(context.already_subscribed_users).map(
                  (user, user_index, user_array) =>
                      html`${user_index === 0
                              ? html` ${$t({defaultMessage: "Already subscribed users:"})} `
                              : ""}
                          <a data-user-id="${user.user_id}" class="view_user_profile"
                              >${user.full_name}</a
                          >${user_index !== user_array.length - 1 ? "," : "."} `,
              )} <br /> `
        : ""}${to_bool(context.ignored_deactivated_users)
        ? to_array(context.ignored_deactivated_users).map(
              (user, user_index, user_array) =>
                  html`${user_index === 0
                          ? html` ${$t({defaultMessage: "Ignored deactivated users:"})} `
                          : ""}
                      <a data-user-id="${user.user_id}" class="view_user_profile"
                          >${user.full_name}</a
                      >${user_index !== user_array.length - 1 ? "," : "."} `,
          )
        : ""}`;
    return to_html(out);
}

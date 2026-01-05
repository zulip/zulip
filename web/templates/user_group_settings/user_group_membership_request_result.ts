import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_user_group_membership_request_result(context) {
    const out = to_bool(context.error_message)
        ? html` ${context.error_message} `
        : context.newly_added_member_count === 0 && context.ignored_deactivated_member_count === 0
          ? to_bool(context.already_added_user_count) &&
            to_bool(context.already_added_subgroups_count)
              ? html` ${$t({defaultMessage: "All users and groups were already members."})} `
              : to_bool(context.already_added_user_count)
                ? html` ${$t({defaultMessage: "All users were already members."})} `
                : html` ${$t({defaultMessage: "All groups were already members."})} `
          : !to_bool(context.total_member_count_exceeds_five)
            ? html`${to_bool(context.addition_success_messages.newly_added_members_message_html)
                  ? html`
                        ${$t({defaultMessage: "Added:"})}
                        ${{
                            __html: context.addition_success_messages
                                .newly_added_members_message_html,
                        }}.&nbsp;
                    `
                  : ""}${to_bool(
                  context.addition_success_messages.already_added_members_message_html,
              )
                  ? html`
                        ${$t({defaultMessage: "Already a member:"})}
                        ${{
                            __html: context.addition_success_messages
                                .already_added_members_message_html,
                        }}.
                    `
                  : ""}${to_bool(
                  context.addition_success_messages.ignored_deactivated_users_message_html,
              )
                  ? html`
                        ${$t({defaultMessage: "Ignored deactivated users:"})}
                        ${{
                            __html: context.addition_success_messages
                                .ignored_deactivated_users_message_html,
                        }}.
                    `
                  : ""}${to_bool(
                  context.addition_success_messages.ignored_deactivated_groups_message_html,
              )
                  ? html`
                        ${$t({defaultMessage: "Ignored deactivated groups:"})}
                        ${{
                            __html: context.addition_success_messages
                                .ignored_deactivated_groups_message_html,
                        }}.
                    `
                  : ""}`
            : html`${to_bool(context.newly_added_member_count)
                  ? html` ${$t({defaultMessage: "Added:"})}
                    ${to_bool(context.newly_added_user_count) &&
                    to_bool(context.newly_added_subgroups_count)
                        ? html`
                              ${$t(
                                  {
                                      defaultMessage:
                                          "{newly_added_user_count, plural, one {# user} other {# users}} and {newly_added_subgroups_count, plural, one {# group.} other {# groups.}}",
                                  },
                                  {
                                      newly_added_user_count: context.newly_added_user_count,
                                      newly_added_subgroups_count:
                                          context.newly_added_subgroups_count,
                                  },
                              )}
                          `
                        : to_bool(context.newly_added_user_count)
                          ? html`
                                ${$t(
                                    {
                                        defaultMessage:
                                            "{newly_added_user_count, plural, one {# user.} other {# users.}}",
                                    },
                                    {newly_added_user_count: context.newly_added_user_count},
                                )}
                            `
                          : to_bool(context.newly_added_subgroups_count)
                            ? html`
                                  ${$t(
                                      {
                                          defaultMessage:
                                              "{newly_added_subgroups_count, plural, one {# group.} other {# groups.}}",
                                      },
                                      {
                                          newly_added_subgroups_count:
                                              context.newly_added_subgroups_count,
                                      },
                                  )}
                              `
                            : ""}`
                  : ""}${to_bool(context.already_added_member_count)
                  ? html` ${$t({defaultMessage: "Already a member:"})}
                    ${to_bool(context.already_added_user_count) &&
                    to_bool(context.already_added_subgroups_count)
                        ? html`
                              ${$t(
                                  {
                                      defaultMessage:
                                          "{already_added_user_count, plural, one {# user} other {# users}} and {already_added_subgroups_count, plural, one {# group.} other {# groups.}}",
                                  },
                                  {
                                      already_added_user_count: context.already_added_user_count,
                                      already_added_subgroups_count:
                                          context.already_added_subgroups_count,
                                  },
                              )}
                          `
                        : to_bool(context.already_added_user_count)
                          ? html`
                                ${$t(
                                    {
                                        defaultMessage:
                                            "{already_added_user_count, plural, one {# user.} other {# users.}}",
                                    },
                                    {already_added_user_count: context.already_added_user_count},
                                )}
                            `
                          : to_bool(context.already_added_subgroups_count)
                            ? html`
                                  ${$t(
                                      {
                                          defaultMessage:
                                              "{already_added_subgroups_count, plural, one {# group.} other {# groups.}}",
                                      },
                                      {
                                          already_added_subgroups_count:
                                              context.already_added_subgroups_count,
                                      },
                                  )}
                              `
                            : ""}`
                  : ""}${to_bool(context.ignored_deactivated_member_count)
                  ? html` ${$t({defaultMessage: "Ignored deactivated:"})}
                    ${to_bool(context.ignored_deactivated_users_count) &&
                    to_bool(context.ignored_deactivated_groups_count)
                        ? html`
                              ${$t(
                                  {
                                      defaultMessage:
                                          "{ignored_deactivated_users_count, plural, one {# user} other {# users}} and {ignored_deactivated_groups_count, plural, one {# group.} other {# groups.}}",
                                  },
                                  {
                                      ignored_deactivated_users_count:
                                          context.ignored_deactivated_users_count,
                                      ignored_deactivated_groups_count:
                                          context.ignored_deactivated_groups_count,
                                  },
                              )}
                          `
                        : to_bool(context.ignored_deactivated_users_count)
                          ? html`
                                ${$t(
                                    {
                                        defaultMessage:
                                            "{ignored_deactivated_users_count, plural, one {# user.} other {# users.}}",
                                    },
                                    {
                                        ignored_deactivated_users_count:
                                            context.ignored_deactivated_users_count,
                                    },
                                )}
                            `
                          : to_bool(context.ignored_deactivated_groups_count)
                            ? html`
                                  ${$t(
                                      {
                                          defaultMessage:
                                              "{ignored_deactivated_groups_count, plural, one {# group.} other {# groups.}}",
                                      },
                                      {
                                          ignored_deactivated_groups_count:
                                              context.ignored_deactivated_groups_count,
                                      },
                                  )}
                              `
                            : ""}`
                  : ""}`;
    return to_html(out);
}

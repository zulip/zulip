import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_stream_subscription_request_result(context) {
    const out = to_bool(context.error_message)
        ? html` ${context.error_message} `
        : /* We want to show ignored deactivated users message even when there are
    no new subscribers */ context.subscribed_users_count === 0 &&
            context.ignored_deactivated_users_count === 0
          ? html` ${$t({defaultMessage: "All users were already subscribed."})} `
          : !to_bool(context.is_total_subscriber_more_than_five)
            ? html`${to_bool(context.subscribed_users)
                  ? html`
                        ${$t({defaultMessage: "Subscribed:"})}
                        ${{
                            __html: context.subscribe_success_messages
                                .subscribed_users_message_html,
                        }}.
                    `
                  : ""}${to_bool(context.already_subscribed_users)
                  ? html`
                        ${$t({defaultMessage: "Already a subscriber:"})}
                        ${{
                            __html: context.subscribe_success_messages
                                .already_subscribed_users_message_html,
                        }}.
                    `
                  : ""}${to_bool(context.ignored_deactivated_users)
                  ? html`
                        ${$t({defaultMessage: "Ignored deactivated users:"})}
                        ${{
                            __html: context.subscribe_success_messages
                                .ignored_deactivated_users_message_html,
                        }}.
                    `
                  : ""}`
            : html`${to_bool(context.subscribed_users)
                  ? html`
                        ${$t(
                            {
                                defaultMessage:
                                    "{subscribed_users_count, plural, one {Subscribed: {subscribed_users_count} user.} other {Subscribed: {subscribed_users_count} users.} }",
                            },
                            {subscribed_users_count: context.subscribed_users_count},
                        )}
                    `
                  : ""}${to_bool(context.already_subscribed_users)
                  ? html`
                        ${$t(
                            {
                                defaultMessage:
                                    "{already_subscribed_users_count, plural, one {Already subscribed: {already_subscribed_users_count} user.} other {Already subscribed: {already_subscribed_users_count} users.} }",
                            },
                            {
                                already_subscribed_users_count:
                                    context.already_subscribed_users_count,
                            },
                        )}
                    `
                  : ""}${to_bool(context.ignored_deactivated_users)
                  ? html`
                        ${$t(
                            {
                                defaultMessage:
                                    "{ignored_deactivated_users_count, plural, one {Ignored deactivated: {ignored_deactivated_users_count} user.} other {Ignored deactivated: {ignored_deactivated_users_count} users.} }",
                            },
                            {
                                ignored_deactivated_users_count:
                                    context.ignored_deactivated_users_count,
                            },
                        )}
                    `
                  : ""}`;
    return to_html(out);
}

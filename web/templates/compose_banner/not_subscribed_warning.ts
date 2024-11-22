import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_not_subscribed_warning(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${to_bool(context1.can_subscribe_other_users)
                        ? to_bool(context1.should_add_guest_user_indicator)
                            ? html`
                                  ${$html_t(
                                      {
                                          defaultMessage:
                                              "<strong>{name}</strong> <i>(guest)</i> is not subscribed to this channel. They will not be notified unless you subscribe them.",
                                      },
                                      {name: context1.name},
                                  )}
                              `
                            : html`
                                  ${$html_t(
                                      {
                                          defaultMessage:
                                              "<strong>{name}</strong> is not subscribed to this channel. They will not be notified unless you subscribe them.",
                                      },
                                      {name: context1.name},
                                  )}
                              `
                        : to_bool(context1.should_add_guest_user_indicator)
                          ? html`
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "<strong>{name}</strong> <i>(guest)</i> is not subscribed to this channel. They will not be notified if you mention them.",
                                    },
                                    {name: context1.name},
                                )}
                            `
                          : html`
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "<strong>{name}</strong> is not subscribed to this channel. They will not be notified if you mention them.",
                                    },
                                    {name: context1.name},
                                )}
                            `}
                </p>
            `,
        ),
    };
    return to_html(out);
}

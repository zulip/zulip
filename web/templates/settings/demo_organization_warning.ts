import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_demo_organization_warning(context) {
    const out = to_bool(context.is_demo_organization)
        ? html`<div class="demo-organization-warning">
              ${to_bool(context.is_owner)
                  ? $html_t(
                        {
                            defaultMessage:
                                "This demo organization will be automatically deleted in {days_remaining} days, unless it's <z-link>converted into a permanent organization</z-link>.",
                        },
                        {
                            days_remaining: context.days_remaining,
                            ["z-link"]: (content) =>
                                html`<a
                                    class="convert-demo-organization-button"
                                    role="button"
                                    tabindex="0"
                                    >${content}</a
                                >`,
                        },
                    )
                  : $html_t(
                        {
                            defaultMessage:
                                "This demo organization will be automatically deleted in {days_remaining} days, unless it's <z-link>converted into a permanent organization</z-link>.",
                        },
                        {
                            days_remaining: context.days_remaining,
                            ["z-link"]: (content) =>
                                html`<a
                                    href="/help/demo-organizations"
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    >${content}</a
                                >`,
                        },
                    )}
          </div> `
        : "";
    return to_html(out);
}

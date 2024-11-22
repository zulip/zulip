import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_demo_organization_deadline(context) {
    const out = html`<div data-step="1">
        ${$html_t(
            {
                defaultMessage:
                    "This is a <z-link-general>demo organization</z-link-general> and will be automatically deleted in {days_remaining} days, unless it's <z-link-convert>converted into a permanent organization</z-link-convert>.",
            },
            {
                days_remaining: context.days_remaining,
                ["z-link-general"]: (content) =>
                    html`<a
                        class="alert-link"
                        href="/help/demo-organizations"
                        target="_blank"
                        rel="noopener noreferrer"
                        role="button"
                        tabindex="0"
                        >${content}</a
                    >`,
                ["z-link-convert"]: (content) =>
                    html`<a
                        class="alert-link"
                        href="/help/demo-organizations#convert-a-demo-organization-to-a-permanent-organization"
                        target="_blank"
                        rel="noopener noreferrer"
                        role="button"
                        tabindex="0"
                        >${content}</a
                    >`,
            },
        )}
    </div> `;
    return to_html(out);
}

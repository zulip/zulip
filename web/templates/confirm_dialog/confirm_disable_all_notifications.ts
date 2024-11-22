import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_confirm_disable_all_notifications() {
    const out = html`<p>
            ${$html_t(
                {
                    defaultMessage:
                        'You are about to disable all notifications for direct messages, @&#8209;mentions and alerts, which may cause you to miss messages that require your timely attention. If you would like to temporarily disable all desktop notifications, consider <z-link>turning on "Do not disturb"</z-link> instead.',
                },
                {
                    ["z-link"]: (content) =>
                        html`<a
                            target="_blank"
                            rel="noopener noreferrer"
                            href="/help/do-not-disturb"
                            >${content}</a
                        >`,
                },
            )}
        </p>

        <p>${$t({defaultMessage: "Are you sure you want to continue?"})}</p> `;
    return to_html(out);
}

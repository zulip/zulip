import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_desktop_notifications() {
    const out = html`<div data-step="1">
            ${$html_t(
                {
                    defaultMessage:
                        "Zulip needs your permission to <z-link>enable desktop notifications.</z-link>",
                },
                {
                    ["z-link"]: (content) =>
                        html`<a
                            class="request-desktop-notifications alert-link"
                            role="button"
                            tabindex="0"
                            >${content}</a
                        >`,
                },
            )}
        </div>
        <div data-step="2" style="display: none">
            ${$t({
                defaultMessage:
                    "We strongly recommend enabling desktop notifications. They help Zulip keep your team connected.",
            })}
            <span class="buttons">
                <a class="alert-link request-desktop-notifications" role="button" tabindex="0"
                    >${$t({defaultMessage: "Enable notifications"})}</a
                >
                &bull;
                <a class="alert-link exit" role="button" tabindex="0"
                    >${$t({defaultMessage: "Ask me later"})}</a
                >
                &bull;
                <a class="alert-link reject-notifications" role="button" tabindex="0"
                    >${$t({defaultMessage: "Never ask on this computer"})}</a
                >
            </span>
        </div> `;
    return to_html(out);
}

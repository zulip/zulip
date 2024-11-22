import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";
import render_stream_privacy from "./stream_privacy.ts";

export default function render_change_visibility_policy_button_tooltip(context) {
    const out = html`<div id="change_visibility_policy_button_tooltip">
        <strong>${$t({defaultMessage: "Configure topic notifications"})}</strong>
        <div class="tooltip-inner-content italic">
            <span>
                ${to_bool(context.should_render_privacy_icon)
                    ? $html_t(
                          {
                              defaultMessage:
                                  "Notifications are based on your configuration for <z-stream-name></z-stream-name>.",
                          },
                          {
                              ["z-stream-name"]: () =>
                                  html`<span class="tooltip-privacy-icon"
                                      >${{__html: render_stream_privacy(context)}}<span
                                          class="privacy-tooltip-stream-name"
                                          >${context.name}</span
                                      ></span
                                  >`,
                          },
                      )
                    : html` ${context.current_visibility_policy_str} `}
            </span>
        </div>
    </div> `;
    return to_html(out);
}

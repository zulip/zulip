import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_add_subscribers_form(context) {
    const out = html`<div class="add_subscribers_container add-button-container">
            <div class="pill-container person_picker">
                <div
                    class="input"
                    contenteditable="true"
                    data-placeholder="${$t({defaultMessage: "Add subscribers."})}"
                ></div>
            </div>
            ${!to_bool(context.hide_add_button)
                ? html`
                      <div
                          class="add_subscriber_button_wrapper add-users-button-wrapper inline-block"
                      >
                          ${{
                              __html: render_action_button({
                                  type: "submit",
                                  intent: "brand",
                                  attention: "quiet",
                                  custom_classes: "add-subscriber-button add-users-button",
                                  label: $t({defaultMessage: "Add"}),
                              }),
                          }}
                          ${{
                              __html: render_icon_button({
                                  disabled: true,
                                  custom_classes: "check hidden-below",
                                  intent: "success",
                                  icon: "check",
                              }),
                          }}
                      </div>
                  `
                : ""}
        </div>
        <div class="add-subscribers-subtitle">
            ${$html_t(
                {
                    defaultMessage:
                        "Enter a <z-user-roles-link>user role</z-user-roles-link>, <z-user-groups-link>user group</z-user-groups-link>, or <z-channel-link>#channel</z-channel-link> to add multiple users at once.",
                },
                {
                    ["z-user-roles-link"]: (content) =>
                        html`<a href="/help/user-roles" target="_blank" rel="noopener noreferrer"
                            >${content}</a
                        >`,
                    ["z-user-groups-link"]: (content) =>
                        html`<a href="/help/user-groups" target="_blank" rel="noopener noreferrer"
                            >${content}</a
                        >`,
                    ["z-channel-link"]: (content) =>
                        html`<a
                            href="/help/introduction-to-channels"
                            target="_blank"
                            rel="noopener noreferrer"
                            >${content}</a
                        >`,
                },
            )}
        </div> `;
    return to_html(out);
}

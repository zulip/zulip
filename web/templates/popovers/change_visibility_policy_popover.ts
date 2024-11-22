import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_change_visibility_policy_popover(context) {
    const out = html`<div
        class="popover-menu visibility-policy-popover"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <ul role="menu" class="popover-menu-list">
            <li role="none" class="popover-menu-list-item">
                <div
                    role="group"
                    class="recipient-bar-topic-visibility-switcher tab-picker tab-picker-vertical"
                    aria-label="${$t({defaultMessage: "Topic visibility"})}"
                >
                    <input
                        type="radio"
                        id="select-muted-policy"
                        class="tab-option"
                        name="visibility-policy-select"
                        data-visibility-policy="${context.all_visibility_policies.MUTED}"
                        ${context.visibility_policy === context.all_visibility_policies.MUTED
                            ? "checked"
                            : ""}
                    />
                    <label
                        role="menuitemradio"
                        class="tab-option-content"
                        for="select-muted-policy"
                        tabindex="0"
                    >
                        <i class="zulip-icon zulip-icon-mute-new" aria-hidden="true"></i>
                        <span class="popover-menu-label">${$t({defaultMessage: "Mute"})}</span>
                    </label>
                    <input
                        type="radio"
                        id="select-inherit-policy"
                        class="tab-option"
                        name="visibility-policy-select"
                        data-visibility-policy="${context.all_visibility_policies.INHERIT}"
                        ${context.visibility_policy === context.all_visibility_policies.INHERIT
                            ? "checked"
                            : ""}
                    />
                    <label
                        role="menuitemradio"
                        class="tab-option-content"
                        for="select-inherit-policy"
                        tabindex="0"
                    >
                        <i class="zulip-icon zulip-icon-inherit" aria-hidden="true"></i>
                        <span class="popover-menu-label">${$t({defaultMessage: "Default"})}</span>
                    </label>
                    ${to_bool(context.stream_muted) || to_bool(context.topic_unmuted)
                        ? html`
                              <input
                                  type="radio"
                                  id="select-unmuted-policy"
                                  class="tab-option"
                                  name="visibility-policy-select"
                                  data-visibility-policy="${context.all_visibility_policies
                                      .UNMUTED}"
                                  ${context.visibility_policy ===
                                  context.all_visibility_policies.UNMUTED
                                      ? "checked"
                                      : ""}
                              />
                              <label
                                  role="menuitemradio"
                                  class="tab-option-content"
                                  for="select-unmuted-policy"
                                  tabindex="0"
                              >
                                  <i
                                      class="zulip-icon zulip-icon-unmute-new"
                                      aria-hidden="true"
                                  ></i>
                                  <span class="popover-menu-label"
                                      >${$t({defaultMessage: "Unmute"})}</span
                                  >
                              </label>
                          `
                        : ""}
                    <input
                        type="radio"
                        id="select-followed-policy"
                        class="tab-option"
                        name="visibility-policy-select"
                        data-visibility-policy="${context.all_visibility_policies.FOLLOWED}"
                        ${context.visibility_policy === context.all_visibility_policies.FOLLOWED
                            ? "checked"
                            : ""}
                    />
                    <label
                        role="menuitemradio"
                        class="tab-option-content"
                        for="select-followed-policy"
                        tabindex="0"
                    >
                        <i class="zulip-icon zulip-icon-follow" aria-hidden="true"></i>
                        <span class="popover-menu-label">${$t({defaultMessage: "Follow"})}</span>
                    </label>
                    <span class="slider"></span>
                </div>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}

import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_browse_user_groups_list_item(context) {
    const out = html`<div
        class="group-row ${to_bool(context.deactivated) ? "deactivated-group" : ""}"
        data-group-id="${context.id}"
        data-group-name="${context.name}"
    >
        ${to_bool(context.is_member)
            ? html`
                  <div
                      class="check checked join_leave_button ${!to_bool(context.can_leave)
                          ? "disabled"
                          : ""} ${!to_bool(context.is_direct_member) ? "not-direct-member" : ""}"
                  >
                      <div
                          class="tippy-zulip-tooltip"
                          data-tooltip-template-id="${to_bool(context.can_leave)
                              ? to_bool(context.is_direct_member)
                                  ? html`leave-${context.id}-group-tooltip-template`
                                  : html`cannot-leave-${context.id}-because-of-subgroup-tooltip-template`
                              : html`cannot-leave-${context.id}-group-tooltip-template`}"
                      >
                          <template id="leave-${context.id}-group-tooltip-template">
                              <span>
                                  ${$html_t(
                                      {defaultMessage: "Leave group {name}"},
                                      {name: context.name},
                                  )}
                              </span>
                          </template>

                          <template
                              id="cannot-leave-${context.id}-because-of-subgroup-tooltip-template"
                          >
                              <span>
                                  ${$html_t(
                                      {
                                          defaultMessage:
                                              "You are a member of this group because you are a member of a subgroup (<z-highlight>{associated_subgroup_names}</z-highlight>).",
                                      },
                                      {
                                          associated_subgroup_names:
                                              context.associated_subgroup_names,
                                          ["z-highlight"]: (content) =>
                                              html`<b class="highlighted-element">${content}</b>`,
                                      },
                                  )}
                              </span>
                          </template>

                          <template id="cannot-leave-${context.id}-group-tooltip-template">
                              ${to_bool(context.deactivated)
                                  ? html`
                                        <span>
                                            ${$html_t({
                                                defaultMessage:
                                                    "You cannot leave a deactivated user group.",
                                            })}
                                        </span>
                                    `
                                  : html`
                                        <span>
                                            ${$html_t({
                                                defaultMessage:
                                                    "You do not have permission to leave this group.",
                                            })}
                                        </span>
                                    `}
                          </template>

                          <i class="zulip-icon zulip-icon-subscriber-check sub-unsub-icon"></i>
                      </div>
                      <div class="join_leave_status"></div>
                  </div>
              `
            : html`
                  <div
                      class="check join_leave_button ${!to_bool(context.can_join)
                          ? "disabled"
                          : ""}"
                  >
                      <div
                          class="tippy-zulip-tooltip"
                          data-tooltip-template-id="${to_bool(context.can_join)
                              ? html`join-${context.id}-group-tooltip-template`
                              : html`cannot-join-${context.id}-group-tooltip-template`}"
                      >
                          <template id="join-${context.id}-group-tooltip-template">
                              <span>
                                  ${$html_t(
                                      {defaultMessage: "Join group {name}"},
                                      {name: context.name},
                                  )}
                              </span>
                          </template>

                          <template id="cannot-join-${context.id}-group-tooltip-template">
                              ${to_bool(context.deactivated)
                                  ? html`
                                        <span>
                                            ${$html_t({
                                                defaultMessage:
                                                    "You cannot join a deactivated user group.",
                                            })}
                                        </span>
                                    `
                                  : html`
                                        <span>
                                            ${$html_t({
                                                defaultMessage:
                                                    "You do not have permission to join this group.",
                                            })}
                                        </span>
                                    `}
                          </template>

                          <i class="zulip-icon zulip-icon-subscriber-plus sub-unsub-icon"></i>
                      </div>
                      <div class="join_leave_status"></div>
                  </div>
              `}
        <div class="group-info-box">
            <div class="top-bar">
                <div class="group-name-wrapper">
                    <div class="group-name">${context.name}</div>
                    ${to_bool(context.deactivated)
                        ? html` <i class="fa fa-ban deactivated-user-icon"></i> `
                        : ""}
                </div>
            </div>
            <div class="bottom-bar">
                <div
                    class="description rendered_markdown"
                    data-no-description="${$t({defaultMessage: "No description."})}"
                >
                    ${context.description}
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_browse_user_groups_list_item(context) {
    const out = html`<div
        class="group-row"
        data-group-id="${context.id}"
        data-group-name="${context.name}"
    >
        ${to_bool(context.is_member)
            ? html`
                  <div
                      class="check checked join_leave_button tippy-zulip-tooltip ${!to_bool(
                          context.can_leave,
                      )
                          ? "disabled"
                          : ""}"
                      data-tooltip-template-id="${to_bool(context.can_leave)
                          ? html`leave-${context.name}-group-tooltip-template`
                          : html`cannot-leave-${context.name}-group-tooltip-template`}"
                  >
                      <template id="leave-${context.name}-group-tooltip-template">
                          <span>
                              ${$html_t(
                                  {defaultMessage: "Leave group {name}"},
                                  {name: context.name},
                              )}
                          </span>
                      </template>

                      <template id="cannot-leave-${context.name}-group-tooltip-template">
                          <span>
                              ${$html_t({
                                  defaultMessage: "You do not have permission to leave this group.",
                              })}
                          </span>
                      </template>

                      <svg
                          version="1.1"
                          xmlns="http://www.w3.org/2000/svg"
                          xmlns:xlink="http://www.w3.org/1999/xlink"
                          x="0px"
                          y="0px"
                          width="100%"
                          height="100%"
                          viewBox="0 0 512 512"
                          style="enable-background:new 0 0 512 512;"
                          xml:space="preserve"
                      >
                          <path
                              d="M448,71.9c-17.3-13.4-41.5-9.3-54.1,9.1L214,344.2l-99.1-107.3c-14.6-16.6-39.1-17.4-54.7-1.8 c-15.6,15.5-16.4,41.6-1.7,58.1c0,0,120.4,133.6,137.7,147c17.3,13.4,41.5,9.3,54.1-9.1l206.3-301.7 C469.2,110.9,465.3,85.2,448,71.9z"
                          />
                      </svg>
                      <div class="join_leave_status"></div>
                  </div>
              `
            : html`
                  <div
                      class="check join_leave_button ${!to_bool(context.can_join)
                          ? "disabled"
                          : ""} tippy-zulip-tooltip"
                      data-tooltip-template-id="${to_bool(context.can_join)
                          ? html`join-${context.name}-group-tooltip-template`
                          : html`cannot-join-${context.name}-group-tooltip-template`}"
                  >
                      <template id="join-${context.name}-group-tooltip-template">
                          <span>
                              ${$html_t(
                                  {defaultMessage: "Join group {name}"},
                                  {name: context.name},
                              )}
                          </span>
                      </template>

                      <template id="cannot-join-${context.name}-group-tooltip-template">
                          <span>
                              ${$html_t({
                                  defaultMessage: "You do not have permission to join this group.",
                              })}
                          </span>
                      </template>

                      <svg
                          version="1.1"
                          xmlns="http://www.w3.org/2000/svg"
                          xmlns:xlink="http://www.w3.org/1999/xlink"
                          x="0px"
                          y="0px"
                          width="100%"
                          height="100%"
                          viewBox="0 0 512 512"
                          style="enable-background:new 0 0 512 512;"
                          xml:space="preserve"
                      >
                          <path
                              d="M459.319,229.668c0,22.201-17.992,40.193-40.205,40.193H269.85v149.271c0,22.207-17.998,40.199-40.196,40.193   c-11.101,0-21.149-4.492-28.416-11.763c-7.276-7.281-11.774-17.324-11.769-28.419l-0.006-149.288H40.181   c-11.094,0-21.134-4.492-28.416-11.774c-7.264-7.264-11.759-17.312-11.759-28.413C0,207.471,17.992,189.475,40.202,189.475h149.267   V40.202C189.469,17.998,207.471,0,229.671,0c22.192,0.006,40.178,17.986,40.19,40.187v149.288h149.282   C441.339,189.487,459.308,207.471,459.319,229.668z"
                          />
                      </svg>
                      <div class="join_leave_status"></div>
                  </div>
              `}
        <div class="group-info-box">
            <div class="top-bar">
                <div class="group-name">${context.name}</div>
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

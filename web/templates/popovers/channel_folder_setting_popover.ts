import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_channel_folder_setting_popover(context) {
    const out = html`<div class="popover-menu" data-simplebar data-simplebar-tab-index="-1">
        <ul role="menu" class="popover-menu-list">
            ${to_bool(context.show_collapse_expand_all_options)
                ? html`
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              id="left_sidebar_expand_all"
                              class="popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-expand"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Expand all sections"})}</span
                              >
                          </a>
                      </li>
                      <li role="none" class="link-item popover-menu-list-item">
                          <a
                              role="menuitem"
                              id="left_sidebar_collapse_all"
                              class="popover-menu-link"
                              tabindex="0"
                          >
                              <i
                                  class="popover-menu-icon zulip-icon zulip-icon-collapse"
                                  aria-hidden="true"
                              ></i>
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Collapse all sections"})}</span
                              >
                          </a>
                      </li>
                  `
                : ""}
            <li role="none" class="link-item popover-menu-list-item">
                <a
                    role="menuitem"
                    id="${context.channel_folders_id}"
                    class="popover-menu-link"
                    tabindex="0"
                >
                    <i
                        class="popover-menu-icon zulip-icon zulip-icon-folder"
                        aria-hidden="true"
                    ></i>
                    ${to_bool(context.show_channel_folders)
                        ? html`
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Don't group channels by folder"})}</span
                              >
                          `
                        : html`
                              <span class="popover-menu-label"
                                  >${$t({defaultMessage: "Group channels by folder"})}</span
                              >
                          `}
                </a>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}

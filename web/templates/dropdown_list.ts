import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";
import render_inline_decorated_channel_name from "./inline_decorated_channel_name.ts";

export default function render_dropdown_list(context) {
    const out = ((item) => html`
        <li
            class="list-item ${to_bool(item.is_current_user_setting) ? "current_user_setting" : ""}"
            role="presentation"
            data-unique-id="${item.unique_id}"
            data-name="${item.name}"
            tabindex="0"
        >
            ${to_bool(item.description)
                ? html`
                      <a class="dropdown-list-item-common-styles">
                          <span class="dropdown-list-item-name">
                              ${to_bool(item.bold_current_selection)
                                  ? html` <span class="dropdown-list-text-selected"
                                            >${item.name}</span
                                        >
                                        ${to_bool(item.has_edit_icon) ||
                                        to_bool(item.has_delete_icon)
                                            ? html`
                                                  <span class="dropdown-list-buttons">
                                                      ${to_bool(item.has_edit_icon)
                                                          ? html` ${{
                                                                __html: render_icon_button({
                                                                    ["aria-label"]:
                                                                        item.edit_icon_label,
                                                                    icon: "edit",
                                                                    intent: "neutral",
                                                                    custom_classes:
                                                                        "dropdown-list-edit dropdown-list-control-button",
                                                                }),
                                                            }}`
                                                          : ""}${to_bool(
                                                          item.has_manage_folder_icon,
                                                      )
                                                          ? html` ${{
                                                                __html: render_icon_button({
                                                                    ["aria-label"]:
                                                                        item.manage_folder_icon_label,
                                                                    icon: "folder-cog",
                                                                    intent: "neutral",
                                                                    custom_classes:
                                                                        "dropdown-list-manage-folder dropdown-list-control-button",
                                                                }),
                                                            }}`
                                                          : ""}${to_bool(item.has_delete_icon)
                                                          ? html` ${{
                                                                __html: render_icon_button({
                                                                    ["aria-label"]:
                                                                        item.delete_icon_label,
                                                                    icon: "trash",
                                                                    intent: "danger",
                                                                    custom_classes:
                                                                        "dropdown-list-delete dropdown-list-control-button",
                                                                }),
                                                            }}`
                                                          : ""}
                                                  </span>
                                              `
                                            : ""}`
                                  : html`
                                        <span class="dropdown-list-text-neutral">${item.name}</span>
                                    `}
                          </span>
                          <span class="dropdown-list-item-description line-clamp">
                              ${item.description}
                          </span>
                      </a>
                  `
                : html`
                      <a
                          class="dropdown-list-item-common-styles ${to_bool(
                              item.is_setting_disabled,
                          )
                              ? "setting-disabled-option"
                              : ""}"
                      >
                          ${to_bool(item.stream)
                              ? html` ${{
                                    __html: render_inline_decorated_channel_name({
                                        show_colored_icon: true,
                                        stream: item.stream,
                                    }),
                                }}`
                              : to_bool(item.is_direct_message)
                                ? html`
                                      <i
                                          class="zulip-icon zulip-icon-users channel-privacy-type-icon"
                                      ></i>
                                      <span class="decorated-dm-name">${item.name}</span>
                                  `
                                : to_bool(item.is_setting_disabled)
                                  ? html`${to_bool(item.show_disabled_icon)
                                        ? html`
                                              <i
                                                  class="setting-disabled-option-icon zulip-icon zulip-icon-deactivated-circle"
                                                  aria-hidden="true"
                                              ></i>
                                          `
                                        : ""}${to_bool(item.show_disabled_option_name)
                                        ? html`
                                              <span
                                                  class="setting-disabled-option-text dropdown-list-text-neutral"
                                                  >${item.name}</span
                                              >
                                          `
                                        : html`
                                              <span
                                                  class="setting-disabled-option-text dropdown-list-text-neutral"
                                                  >${$t({defaultMessage: "Disable"})}</span
                                              >
                                          `}`
                                  : item.unique_id === -2
                                    ? /* This is the option for PresetUrlOption.CHANNEL_MAPPING */ html`
                                          <i
                                              class="zulip-icon zulip-icon-hashtag channel-privacy-type-icon"
                                              aria-hidden="true"
                                          ></i>
                                          <span class="dropdown-list-text-neutral"
                                              >${item.name}</span
                                          >
                                      `
                                    : html`
                                          <span class="dropdown-list-item-name">
                                              ${to_bool(item.bold_current_selection)
                                                  ? html`
                                                        <span class="dropdown-list-text-selected"
                                                            >${item.name}</span
                                                        >
                                                    `
                                                  : html`
                                                        <span class="dropdown-list-text-neutral"
                                                            >${item.name}</span
                                                        >
                                                    `}${to_bool(item.has_edit_icon) ||
                                              to_bool(item.has_delete_icon)
                                                  ? html`
                                                        <span class="dropdown-list-buttons">
                                                            ${to_bool(item.has_edit_icon)
                                                                ? html` ${{
                                                                      __html: render_icon_button({
                                                                          ["aria-label"]: $t({
                                                                              defaultMessage:
                                                                                  "Edit folder",
                                                                          }),
                                                                          icon: "edit",
                                                                          intent: "neutral",
                                                                          custom_classes:
                                                                              "dropdown-list-edit dropdown-list-control-button",
                                                                      }),
                                                                  }}`
                                                                : ""}${to_bool(
                                                                item.has_manage_folder_icon,
                                                            )
                                                                ? html` ${{
                                                                      __html: render_icon_button({
                                                                          ["aria-label"]:
                                                                              item.manage_folder_icon_label,
                                                                          icon: "folder-cog",
                                                                          intent: "neutral",
                                                                          custom_classes:
                                                                              "dropdown-list-manage-folder dropdown-list-control-button",
                                                                      }),
                                                                  }}`
                                                                : ""}${to_bool(item.has_delete_icon)
                                                                ? html` ${{
                                                                      __html: render_icon_button({
                                                                          ["aria-label"]: $t({
                                                                              defaultMessage:
                                                                                  "Delete folder",
                                                                          }),
                                                                          icon: "trash",
                                                                          intent: "danger",
                                                                          custom_classes:
                                                                              "dropdown-list-delete dropdown-list-control-button",
                                                                      }),
                                                                  }}`
                                                                : ""}
                                                        </span>
                                                    `
                                                  : ""}
                                          </span>
                                      `}
                      </a>
                  `}
        </li>
    `)(context.item);
    return to_html(out);
}

import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_inline_decorated_stream_name from "./inline_decorated_stream_name.ts";

export default function render_dropdown_list(context) {
    const out = ((item) => html`
        <li
            class="list-item"
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
                                  ? html` <span class="dropdown-list-bold-selected"
                                            >${item.name}</span
                                        >
                                        ${to_bool(item.has_delete_icon)
                                            ? html`
                                                  <span class="dropdown-list-delete">
                                                      <i
                                                          class="fa fa-trash-o dropdown-list-delete-icon"
                                                      ></i>
                                                  </span>
                                              `
                                            : ""}`
                                  : html` ${item.name} `}
                          </span>
                          <span class="dropdown-list-item-description"> ${item.description} </span>
                      </a>
                  `
                : html`
                      <a class="dropdown-list-item-common-styles">
                          ${to_bool(item.stream)
                              ? html` ${{
                                    __html: render_inline_decorated_stream_name({
                                        show_colored_icon: true,
                                        stream: item.stream,
                                    }),
                                }}`
                              : to_bool(item.is_direct_message)
                                ? html`
                                      <i
                                          class="zulip-icon zulip-icon-users stream-privacy-type-icon"
                                      ></i>
                                      ${item.name}
                                  `
                                : to_bool(item.is_setting_disabled)
                                  ? html`
                                        <span class="setting-disabled-option"
                                            ><i
                                                class="setting-disabled-option-icon fa fa-ban"
                                                aria-hidden="true"
                                            ></i
                                            >${$t({defaultMessage: "Disable"})}</span
                                        >
                                    `
                                  : html`${to_bool(item.bold_current_selection)
                                        ? html`
                                              <span class="dropdown-list-bold-selected"
                                                  >${item.name}</span
                                              >
                                          `
                                        : html` ${item.name} `} `}
                      </a>
                  `}
        </li>
    `)(context.item);
    return to_html(out);
}

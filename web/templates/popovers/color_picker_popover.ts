import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_stream_privacy from "../stream_privacy.ts";

export default function render_color_picker_popover(context) {
    const out = html`<div
        class="popover-menu color-picker-popover no-auto-hide-left-sidebar-overlay"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="message_header message_header_stream" data-stream-id="${context.stream_id}">
            <div
                class="message-header-contents"
                style="background: ${context.recipient_bar_color};"
            >
                <div class="message_label_clickable stream_label">
                    <span
                        class="stream-privacy-modified-color-${context.stream_id} stream-privacy filter-icon"
                        style="color: ${context.stream_privacy_icon_color}"
                    >
                        ${{__html: render_stream_privacy(context)}}
                    </span>
                    ${to_bool(context.stream_name)
                        ? html`
                              <span class="message-header-stream-name">${context.stream_name}</span>
                          `
                        : html` &nbsp; `}
                </div>
                <button
                    class="color_picker_confirm_button icon-button icon-button-square icon-button-neutral tippy-zulip-delayed-tooltip"
                    data-tooltip-template-id="color-picker-confirm-button-tooltip-template"
                    aria-label="${$t({defaultMessage: "Confirm new color"})}"
                    tabindex="0"
                >
                    <i class="zulip-icon zulip-icon-check"></i>
                </button>
            </div>
        </div>
        <ul role="menu" class="popover-menu-list">
            <li role="none">
                <div
                    role="group"
                    class="color-swatch-list"
                    aria-label="${$t({defaultMessage: "Stream color"})}"
                >
                    ${to_array(context.stream_color_palette).map((row, row_index) =>
                        to_array(row).map(
                            (hex_color, hex_color_index) => html`
                                <input
                                    type="radio"
                                    id="color-${hex_color}"
                                    class="color-swatch-input"
                                    name="color-picker-select"
                                    data-swatch-color="${hex_color}"
                                    ${hex_color === context.stream_color ? "checked" : ""}
                                />
                                <label
                                    role="menuitemradio"
                                    class="color-swatch-label tippy-zulip-delayed-tooltip"
                                    for="color-${hex_color}"
                                    style="background-color: ${hex_color};"
                                    aria-label="${hex_color}"
                                    data-tippy-content="${hex_color}"
                                    data-swatch-color="${hex_color}"
                                    data-row="${row_index}"
                                    data-column="${hex_color_index}"
                                    tabindex="0"
                                ></label>
                            `,
                        ),
                    )}
                </div>
            </li>
            <li role="separator" class="popover-menu-separator"></li>
            <li role="none" class="link-item popover-menu-list-item">
                <label role="menuitem" class="custom-color-picker popover-menu-link" tabindex="0">
                    <i class="custom-color-swatch-icon popover-menu-icon" aria-hidden="true"></i>
                    <span class="popover-menu-label">${$t({defaultMessage: "Custom color"})}</span>
                    <input
                        type="color"
                        class="color-picker-input"
                        tabindex="-1"
                        value="${context.stream_color}"
                    />
                </label>
            </li>
        </ul>
    </div> `;
    return to_html(out);
}

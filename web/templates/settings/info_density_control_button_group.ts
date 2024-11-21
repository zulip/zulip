import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_info_density_control_button_group(context) {
    const out = html`<div class="button-group" data-property="${context.property}">
        ${to_bool(context.for_settings_ui)
            ? html`
                  <div class="info-density-button-container">
                      <button
                          class="info-density-button default-button"
                          aria-label="${context.property === "web_font_size_px"
                              ? $t({defaultMessage: "Set font size to default"})
                              : $t({defaultMessage: "Set line spacing to default"})}"
                      >
                          <i
                              class="zulip-icon ${context.default_icon_class}"
                              aria-hidden="true"
                          ></i>
                      </button>
                  </div>
              `
            : ""}${to_bool(context.for_settings_ui)
            ? html` <span class="display-value">${context.display_value}</span> `
            : ""}
        <input
            class="current-value prop-element"
            id="${context.prefix}${context.property}"
            data-setting-widget-type="info-density-setting"
            type="hidden"
            value="${context.property_value}"
        />
        <div class="info-density-button-container">
            <button
                class="info-density-button decrease-button"
                aria-label="${context.property === "web_font_size_px"
                    ? $t({defaultMessage: "Decrease font size"})
                    : $t({defaultMessage: "Decrease line spacing"})}"
            >
                <i class="zulip-icon zulip-icon-minus" aria-hidden="true"></i>
            </button>
        </div>
        ${!to_bool(context.for_settings_ui)
            ? html`
                  <div class="info-density-button-container">
                      <button
                          class="info-density-button default-button"
                          aria-label="${context.property === "web_font_size_px"
                              ? $t({defaultMessage: "Set font size to default"})
                              : $t({defaultMessage: "Set line spacing to default"})}"
                      >
                          <i
                              class="zulip-icon ${context.default_icon_class}"
                              aria-hidden="true"
                          ></i>
                      </button>
                  </div>
              `
            : ""}
        <div class="info-density-button-container">
            <button
                class="info-density-button increase-button"
                aria-label="${context.property === "web_font_size_px"
                    ? $t({defaultMessage: "Increase font size"})
                    : $t({defaultMessage: "Increase line spacing"})}"
            >
                <i class="zulip-icon zulip-icon-plus" aria-hidden="true"></i>
            </button>
        </div>
    </div> `;
    return to_html(out);
}

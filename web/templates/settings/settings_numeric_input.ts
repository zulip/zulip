import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_settings_numeric_input(context) {
    const out =
        context.render_only !== false
            ? html`<div
                  class="input-group setting-next-is-related ${to_bool(context.is_disabled)
                      ? "control-label-disabled"
                      : ""}"
              >
                  <label
                      for="${to_bool(context.prefix) ? context.prefix : ""}${context.setting_name}"
                      class="${context.setting_name}_label"
                      id="${to_bool(context.prefix)
                          ? context.prefix
                          : ""}${context.setting_name}_label"
                  >
                      ${context.label}
                      ${to_bool(context.label_parens_text)
                          ? html` (<i>${context.label_parens_text}</i>) `
                          : ""}${to_bool(context.help_link)
                          ? html` ${{__html: render_help_link_widget({link: context.help_link})}}`
                          : ""}${to_bool(context.tooltip_text)
                          ? html`
                                <i
                                    class="tippy-zulip-tooltip fa fa-info-circle settings-info-icon"
                                    ${to_bool(context.hide_tooltip)
                                        ? html`style="display: none;"`
                                        : ""}
                                    data-tippy-content="${context.tooltip_text}"
                                ></i>
                            `
                          : ""}
                  </label>
                  <input
                      type="text"
                      inputmode="numeric"
                      pattern="\\d*"
                      value="${context.setting_value}"
                      class="${context.setting_name} settings_text_input setting-widget prop-element"
                      name="${context.setting_name}"
                      data-setting-widget-type="number"
                      id="${to_bool(context.prefix) ? context.prefix : ""}${context.setting_name}"
                      ${to_bool(context.is_disabled) ? "disabled" : ""}
                  />
              </div> `
            : "";
    return to_html(out);
}

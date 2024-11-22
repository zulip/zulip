import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_preferences_emoji(context) {
    const out = html`<div
        class="emoji-preferences ${to_bool(context.for_realm_settings)
            ? "settings-subsection-parent"
            : "subsection-parent"}"
    >
        <div class="subsection-header">
            <h3 class="light">${$t({defaultMessage: "Emoji"})}</h3>
            ${{
                __html: render_settings_save_discard_widget({
                    show_only_indicator: !to_bool(context.for_realm_settings),
                    section_name: "emoji-preferences-settings",
                }),
            }}
        </div>

        <div class="input-group">
            <label class="settings-field-label">${$t({defaultMessage: "Emoji theme"})}</label>
            <div
                class="emojiset_choices grey-box prop-element"
                id="${context.prefix}emojiset"
                data-setting-widget-type="radio-group"
                data-setting-choice-type="string"
            >
                ${to_array(context.settings_object.emojiset_choices).map(
                    (emojiset) => html`
                        <label class="preferences-radio-choice-label">
                            <div class="radio-choice-controls">
                                <input
                                    type="radio"
                                    class="setting_emojiset_choice"
                                    name="emojiset"
                                    value="${emojiset.key}"
                                />
                                <span class="preferences-radio-choice-text">${emojiset.text}</span>
                                ${emojiset.key === "google-blob"
                                    ? html` <span
                                              >(<em>${$t({
                                                  defaultMessage: "deprecated",
                                              })}</em>)</span
                                          >
                                          ${{
                                              __html: render_help_link_widget({
                                                  link: "/help/emoji-and-emoticons#change-your-emoji-set",
                                              }),
                                          }}`
                                    : ""}
                            </div>
                            <span class="right">
                                ${emojiset.key === "text"
                                    ? html` <div class="emoji_alt_code">&nbsp;:relaxed:</div> `
                                    : html`
                                          <img
                                              class="emoji"
                                              src="/static/generated/emoji/images-${emojiset.key}-64/1f642.png"
                                          />
                                          <img
                                              class="emoji"
                                              src="/static/generated/emoji/images-${emojiset.key}-64/1f44d.png"
                                          />
                                          <img
                                              class="emoji"
                                              src="/static/generated/emoji/images-${emojiset.key}-64/1f680.png"
                                          />
                                          <img
                                              class="emoji"
                                              src="/static/generated/emoji/images-${emojiset.key}-64/1f389.png"
                                          />
                                      `}
                            </span>
                        </label>
                    `,
                )}
            </div>
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                help_link: "/help/configure-emoticon-translations",
                label: context.settings_label.translate_emoticons,
                is_checked: context.settings_object.translate_emoticons,
                setting_name: "translate_emoticons",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                label: context.settings_label.display_emoji_reaction_users,
                is_checked: context.settings_object.display_emoji_reaction_users,
                setting_name: "display_emoji_reaction_users",
            }),
        }}
    </div> `;
    return to_html(out);
}

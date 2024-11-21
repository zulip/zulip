import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_alert_word_settings_item(context) {
    const out = /* Alert word in the settings page that can be removed */ ((alert_word) =>
        html`<tr class="alert-word-item" data-word="${alert_word.word}">
            <td>
                <div class="alert_word_listing">
                    <span class="value">${alert_word.word}</span>
                </div>
            </td>
            <td>
                ${{
                    __html: render_icon_button({
                        ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                        custom_classes: "delete remove-alert-word tippy-zulip-delayed-tooltip",
                        intent: "danger",
                        icon: "trash",
                    }),
                }}
            </td>
        </tr> `)(context.alert_word);
    return to_html(out);
}

import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_alert_word_settings_item(context) {
    const out = /* Alert word in the settings page that can be removed */ ((alert_word) =>
        html`<tr class="alert-word-item" data-word="${alert_word.word}">
            <td>
                <div class="alert_word_listing">
                    <span class="value">${alert_word.word}</span>
                </div>
            </td>
            <td>
                <button
                    type="submit"
                    class="button rounded small delete button-danger remove-alert-word tippy-zulip-delayed-tooltip"
                    data-tippy-content="${$t({defaultMessage: "Delete"})}"
                    data-word="${alert_word.word}"
                >
                    <i class="fa fa-trash-o" aria-hidden="true"></i>
                </button>
            </td>
        </tr> `)(context.alert_word);
    return to_html(out);
}

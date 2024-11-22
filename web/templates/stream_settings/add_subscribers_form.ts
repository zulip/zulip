import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_add_subscribers_form(context) {
    const out = html`<div class="add_subscribers_container">
        <div class="pill-container person_picker">
            <div
                class="input"
                contenteditable="true"
                data-placeholder="${$t({
                    defaultMessage:
                        "Add subscribers. Use usergroup or #channelname to bulk add subscribers.",
                })}"
            ></div>
        </div>
        ${!to_bool(context.hide_add_button)
            ? html`
                  <div class="add_subscriber_button_wrapper inline-block">
                      <button
                          type="submit"
                          name="add_subscriber"
                          class="button add-subscriber-button add-users-button small rounded sea-green"
                          tabindex="0"
                      >
                          ${$t({defaultMessage: "Add"})}
                      </button>
                  </div>
              `
            : ""}
    </div> `;
    return to_html(out);
}

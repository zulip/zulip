import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_add_members_form(context) {
    const out = html`<div class="add_members_container">
        <div class="pill-container person_picker">
            <div
                class="input"
                contenteditable="true"
                data-placeholder="${$t({
                    defaultMessage: "Add users or groups. Use #channelname to add all subscribers.",
                })}"
            ></div>
        </div>
        ${!to_bool(context.hide_add_button)
            ? html`
                  <div class="add_member_button_wrapper inline-block">
                      <button
                          type="submit"
                          name="add_member"
                          class="button add-member-button add-users-button small rounded sea-green"
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

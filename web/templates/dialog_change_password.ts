import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_dialog_change_password(context) {
    const out = html`<form id="change_password_container">
        <div class="settings-password-div">
            <label for="old_password" class="modal-field-label"
                >${$t({defaultMessage: "Old password"})}</label
            >
            <div class="password-input-row">
                <input
                    type="password"
                    autocomplete="off"
                    name="old_password"
                    id="old_password"
                    class="inline-block modal_password_input"
                    value=""
                />
                <i
                    class="fa fa-eye-slash password_visibility_toggle tippy-zulip-tooltip"
                    role="button"
                    tabindex="0"
                ></i>
                <a
                    href="/accounts/password/reset/"
                    class="settings-forgot-password sea-green"
                    target="_blank"
                    rel="noopener noreferrer"
                    >${$t({defaultMessage: "Forgot it?"})}</a
                >
            </div>
        </div>
        <div class="settings-password-div">
            <label for="new_password" class="modal-field-label"
                >${$t({defaultMessage: "New password"})}</label
            >
            <div class="password-input-row">
                <input
                    type="password"
                    autocomplete="new-password"
                    name="new_password"
                    id="new_password"
                    class="inline-block modal_password_input"
                    value=""
                    data-min-length="${context.password_min_length}"
                    data-min-guesses="${context.password_min_guesses}"
                />
                <i
                    class="fa fa-eye-slash password_visibility_toggle tippy-zulip-tooltip"
                    role="button"
                    tabindex="0"
                ></i>
            </div>
            <div class="progress inline-block" id="pw_strength">
                <div class="bar bar-danger hide" style="width: 10%;"></div>
            </div>
        </div>
    </form> `;
    return to_html(out);
}

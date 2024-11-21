import {html, to_html} from "../../shared/src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_api_key_modal() {
    const out = html`<div class="micromodal" id="api_key_modal" aria-hidden="true">
        <div class="modal__overlay" tabindex="-1">
            <div
                class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="api_key_modal_label"
            >
                <header class="modal__header">
                    <h1 class="modal__title" id="api_key_modal_label">
                        ${$t({defaultMessage: "Show API key"})}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </header>
                <main class="modal__content">
                    <div id="password_confirmation">
                        <span class="alert-notification" id="api_key_status"></span>
                        <div id="api_key_form">
                            <p>
                                ${$t({
                                    defaultMessage:
                                        "Please re-enter your password to confirm your identity.",
                                })}
                            </p>
                            <div class="settings-password-div">
                                <label for="get_api_key_password" class="modal-field-label"
                                    >${$t({defaultMessage: "Your password"})}</label
                                >
                                <div class="password-input-row">
                                    <input
                                        type="password"
                                        autocomplete="off"
                                        name="password"
                                        id="get_api_key_password"
                                        class=" modal_password_input"
                                        value=""
                                    />
                                    <i
                                        class="fa fa-eye-slash password_visibility_toggle tippy-zulip-tooltip"
                                        role="button"
                                    ></i>
                                </div>
                            </div>
                            <p class="small">
                                ${$html_t(
                                    {
                                        defaultMessage:
                                            "If you don't know your password, you can <z-link>reset it</z-link>.",
                                    },
                                    {
                                        ["z-link"]: (content) =>
                                            html`<a
                                                href="/accounts/password/reset/"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                >${content}</a
                                            >`,
                                    },
                                )}
                            </p>
                        </div>
                    </div>
                    <div id="show_api_key">
                        <p>${$t({defaultMessage: "Your API key:"})}</p>
                        <p>
                            <b><span id="api_key_value"></span></b>
                        </p>
                        <div id="user_api_key_error" class="text-error"></div>
                    </div>
                </main>
                <footer class="modal__footer">
                    <button
                        type="submit"
                        name="view_api_key"
                        id="get_api_key_button"
                        class="modal__button dialog_submit_button"
                    >
                        ${$t({defaultMessage: "Get API key"})}
                    </button>
                    <div id="api_key_buttons">
                        <button
                            class="modal__button dialog_submit_button"
                            id="regenerate_api_key"
                            aria-label="${$t({defaultMessage: "Generate new API key"})}"
                        >
                            ${$t({defaultMessage: "Generate new API key"})}
                        </button>
                        <a
                            class="modal__button dialog_submit_button"
                            id="download_zuliprc"
                            download="zuliprc"
                            tabindex="0"
                            >${$t({defaultMessage: "Download zuliprc"})}</a
                        >
                    </div>
                </footer>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

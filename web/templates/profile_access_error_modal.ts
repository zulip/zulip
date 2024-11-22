import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_profile_access_error_modal() {
    const out = html`<div class="micromodal" id="profile_access_error_modal" aria-hidden="true">
        <div class="modal__overlay" tabindex="-1">
            <div
                class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="profile_access_error_modal_label"
            >
                <header class="modal__header">
                    <h1 class="modal__title" id="profile_access_error_modal_label">
                        ${$t({defaultMessage: "No user found"})}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </header>
                <main class="modal__content">
                    <p>
                        ${$t({
                            defaultMessage:
                                "Either this user does not exist, or you do not have access to their profile.",
                        })}
                    </p>
                </main>
                <footer class="modal__footer">
                    <button
                        type="button"
                        class="modal__button dialog_exit_button"
                        aria-label="${$t({defaultMessage: "Close this dialog window"})}"
                        data-micromodal-close
                    >
                        ${$t({defaultMessage: "Close"})}
                    </button>
                </footer>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

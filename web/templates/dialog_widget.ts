import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_dialog_widget(context) {
    const out = html`<div class="micromodal" id="${context.modal_unique_id}" aria-hidden="true">
        <div class="modal__overlay" tabindex="-1">
            <div
                ${to_bool(context.id) ? html`id="${context.id}" ` : ""}class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="dialog_title"
            >
                <header class="modal__header">
                    <h1 class="modal__title dialog_heading">
                        ${{__html: context.heading_text}}
                        ${to_bool(context.link)
                            ? html` ${{__html: render_help_link_widget(context)}}`
                            : ""}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </header>
                <main
                    class="modal__content"
                    data-simplebar
                    data-simplebar-tab-index="-1"
                    ${to_bool(context.always_visible_scrollbar)
                        ? html`data-simplebar-auto-hide="false"`
                        : ""}
                >
                    <div class="alert" id="dialog_error"></div>
                    ${{__html: context.html_body}}
                </main>
                <footer class="modal__footer">
                    ${!to_bool(context.single_footer_button)
                        ? html`
                              <button
                                  class="modal__button dialog_exit_button"
                                  aria-label="${$t({defaultMessage: "Close this dialog window"})}"
                                  data-micromodal-close
                              >
                                  ${{__html: context.html_exit_button}}
                              </button>
                          `
                        : ""}
                    <div class="dialog_submit_button_container">
                        <button
                            class="modal__button dialog_submit_button"
                            ${to_bool(context.single_footer_button)
                                ? html` aria-label="${$t({
                                      defaultMessage: "Close this dialog window",
                                  })}"
                                  data-micromodal-close`
                                : ""}
                        >
                            <span class="submit-button-text"
                                >${{__html: context.html_submit_button}}</span
                            >
                            <div class="modal__spinner"></div>
                        </button>
                    </div>
                </footer>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_dialog_widget(context) {
    const out = html`<div class="micromodal" id="${context.modal_unique_id}" aria-hidden="true">
        <div
            class="modal__overlay ${!to_bool(context.close_on_overlay_click)
                ? "ignore-overlay-click"
                : ""}"
            tabindex="-1"
        >
            <div
                ${to_bool(context.id) ? html`id="${context.id}" ` : ""}class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="dialog_title"
            >
                <header class="modal__header">
                    <h1 class="modal__title dialog_heading">
                        ${to_bool(context.heading_html)
                            ? html` ${{__html: context.heading_html}} `
                            : html` ${context.text_heading} `}${to_bool(context.link)
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
                    ${{__html: context.body_html}}
                </main>
                <footer class="modal__footer">
                    ${to_bool(context.footer_minor_text)
                        ? html`
                              <div class="dialog-widget-footer-minor-text">
                                  ${context.footer_minor_text}
                              </div>
                          `
                        : ""}${!to_bool(context.single_footer_button)
                        ? html`
                              <button
                                  class="modal__button dialog_exit_button"
                                  aria-label="${$t({defaultMessage: "Close this dialog window"})}"
                                  data-micromodal-close
                              >
                                  ${{__html: context.exit_button_html}}
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
                                >${{__html: context.submit_button_html}}</span
                            >
                            <span class="modal__spinner"></span>
                        </button>
                    </div>
                </footer>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

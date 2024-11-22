import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";
import render_send_later_modal_options from "./send_later_modal_options.ts";

export default function render_send_later_modal(context) {
    const out = html`<div class="micromodal" id="send_later_modal" aria-hidden="true">
        <div class="modal__overlay" tabindex="-1">
            <div
                class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="send_later_modal_label"
            >
                <header class="modal__header">
                    <h1 class="modal__title" id="send_later_modal_label">
                        ${$t({defaultMessage: "Schedule message"})}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </header>
                <main class="modal__content">
                    ${{__html: render_send_later_modal_options(context)}}
                </main>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

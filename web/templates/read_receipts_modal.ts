import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_read_receipts_modal(context) {
    const out = html`<div
        class="micromodal"
        id="read_receipts_modal"
        aria-hidden="true"
        data-message-id="${context.message_id}"
    >
        <div class="modal__overlay" tabindex="-1">
            <div
                class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="read_receipts_modal_label"
            >
                <header class="modal__header">
                    <h1 class="modal__title" id="read_receipts_modal_label">
                        ${$t({defaultMessage: "Read receipts"})}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </header>
                <hr />
                <main class="modal__content">
                    <div class="alert" id="read_receipts_error"></div>
                    <div class="read_receipts_info"></div>
                    <div class="loading_indicator"></div>
                    <ul class="read_receipts_list"></ul>
                </main>
            </div>
        </div>
    </div> `;
    return to_html(out);
}

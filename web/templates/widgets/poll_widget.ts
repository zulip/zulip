import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_poll_widget() {
    const out = html`<div class="poll-widget">
        <div class="poll-widget-header-area">
            <h4 class="poll-question-header"></h4>
            <i class="fa fa-pencil poll-edit-question"></i>
            <div class="poll-question-bar">
                <input
                    type="text"
                    class="poll-question"
                    placeholder="${$t({defaultMessage: "Add question"})}"
                />
                <button class="poll-question-remove"><i class="fa fa-remove"></i></button>
                <button class="poll-question-check"><i class="fa fa-check"></i></button>
            </div>
        </div>
        <div class="poll-please-wait">
            ${$t({defaultMessage: "We are about to have a poll.  Please wait for the question."})}
        </div>
        <div class="poll-author-help">
            ${$t({defaultMessage: 'Tip: You can also send "/poll Some question"'})}
        </div>
        <ul class="poll-widget"></ul>
        <div class="poll-option-bar">
            <input
                type="text"
                class="poll-option"
                placeholder="${$t({defaultMessage: "New option"})}"
            />
            <button class="poll-option">${$t({defaultMessage: "Add option"})}</button>
        </div>
    </div> `;
    return to_html(out);
}

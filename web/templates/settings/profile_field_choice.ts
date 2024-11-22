import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_profile_field_choice(context) {
    const out = html`<div class="choice-row movable-row" data-value="${context.value}">
        <span class="move-handle">
            <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
            <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
        </span>
        <input
            type="text"
            class="modal_text_input"
            placeholder="${$t({defaultMessage: "New option"})}"
            value="${context.text}"
        />

        <button
            type="button"
            class="button rounded small delete-choice tippy-zulip-tooltip ${to_bool(
                context.new_empty_choice_row,
            )
                ? " hide "
                : ""}"
            data-tippy-content="${$t({defaultMessage: "Delete"})}"
        >
            <i class="fa fa-trash-o" aria-hidden="true"></i>
        </button>
    </div> `;
    return to_html(out);
}

import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_icon_button from "../components/icon_button.ts";

export default function render_profile_field_choice(context) {
    const out = html`<div class="choice-row movable-row" data-value="${context.value}">
        <span class="move-handle ${to_bool(context.new_empty_choice_row) ? "invisible" : ""}">
            <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
            <i class="fa fa-ellipsis-v" aria-hidden="true"></i>
        </span>
        <input
            type="text"
            class="modal_text_input"
            placeholder="${$t({defaultMessage: "New option"})}"
            value="${context.text}"
        />
        ${{
            __html: render_icon_button({
                ["aria-label"]: $t({defaultMessage: "Delete"}),
                ["data-tippy-content"]: $t({defaultMessage: "Delete"}),
                icon: "trash",
                hidden: context.new_empty_choice_row,
                custom_classes: "delete-choice tippy-zulip-tooltip",
                intent: "danger",
            }),
        }}
    </div> `;
    return to_html(out);
}

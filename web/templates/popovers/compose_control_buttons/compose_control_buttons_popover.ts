import {html, to_html} from "../../../shared/src/html.ts";
import {to_bool} from "../../../src/hbs_compat.ts";
import render_compose_control_buttons_in_popover from "./compose_control_buttons_in_popover.ts";
import render_compose_control_buttons_in_popover_2 from "./compose_control_buttons_in_popover_2.ts";

export default function render_compose_control_buttons_popover(context) {
    const out = html`<div
        class="compose-control-buttons-container order-1 ${to_bool(context.preview_mode_on)
            ? " preview_mode "
            : ""}"
    >
        ${{__html: render_compose_control_buttons_in_popover_2(context)}}
        ${{__html: render_compose_control_buttons_in_popover(context)}}
    </div> `;
    return to_html(out);
}

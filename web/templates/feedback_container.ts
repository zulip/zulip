import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_feedback_container(context) {
    const out = html`<div class="float-header">
            <h3 class="light no-margin small-line-height float-left feedback_title"></h3>
            <div class="exit-me float-right">&#215;</div>
            ${to_bool(context.has_undo_button)
                ? html`
                      <button
                          class="button small rounded float-right feedback_undo"
                          type="button"
                          name="button"
                      ></button>
                  `
                : ""}
            <div class="float-clear"></div>
        </div>
        <p class="n-margin feedback_content"></p> `;
    return to_html(out);
}

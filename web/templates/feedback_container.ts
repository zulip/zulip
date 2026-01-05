import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import render_action_button from "./components/action_button.ts";
import render_icon_button from "./components/icon_button.ts";

export default function render_feedback_container(context) {
    const out = html`<div id="feedback-container-content-wrapper">
        <div class="float-header">
            <h3 class="light no-margin small-line-height float-left feedback_title"></h3>
            <div class="feedback-button-container">
                ${to_bool(context.has_undo_button)
                    ? html` ${{
                          __html: render_action_button({
                              custom_classes: "feedback_undo",
                              attention: "quiet",
                              intent: "neutral",
                          }),
                      }}`
                    : ""}
                ${{
                    __html: render_icon_button({
                        icon: "close",
                        custom_classes: "exit-me",
                        intent: "neutral",
                    }),
                }}
            </div>
            <div class="float-clear"></div>
        </div>
        <p class="n-margin feedback_content"></p>
    </div> `;
    return to_html(out);
}

import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import render_action_button from "./components/action_button.ts";
import render_topic_not_mandatory_placeholder_text from "./topic_not_mandatory_placeholder_text.ts";

export default function render_topic_edit_form(context) {
    const out = /* Client-side Handlebars template for rendering the topic edit form. */ html`
        <form class="topic_edit_form">
            <span class="topic_value_mirror hide"></span>
            <input
                type="text"
                value=""
                autocomplete="off"
                maxlength="${context.max_topic_length}"
                class="inline_topic_edit header-v"
            />
            ${!to_bool(context.is_mandatory_topics)
                ? html`
                      <span class="inline-topic-edit-placeholder placeholder">
                          ${{
                              __html: render_topic_not_mandatory_placeholder_text({
                                  empty_string_topic_display_name:
                                      context.empty_string_topic_display_name,
                              }),
                          }}
                      </span>
                  `
                : ""}
            <span class="topic-edit-save-wrapper">
                ${{
                    __html: render_action_button({
                        ["data-tooltip-template-id"]: "save-button-tooltip-template",
                        intent: "neutral",
                        attention: "quiet",
                        icon: "check",
                        custom_classes: "topic_edit_save tippy-zulip-delayed-tooltip",
                    }),
                }}
            </span>
            ${{
                __html: render_action_button({
                    ["data-tooltip-template-id"]: "cancel-button-tooltip-template",
                    intent: "neutral",
                    attention: "borderless",
                    icon: "circle-x",
                    custom_classes: "topic_edit_cancel tippy-zulip-delayed-tooltip",
                }),
            }}
            <div class="topic_edit_spinner"></div>
        </form>
    `;
    return to_html(out);
}

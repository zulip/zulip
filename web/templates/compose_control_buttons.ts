import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_compose_control_buttons(context) {
    const out = html`<div
        class="compose-scrollable-buttons compose-control-buttons-container order-1"
        tabindex="-1"
    >
        <input type="file" class="file_input notvisible" multiple />
        <div
            class="compose_control_button_container compose_button_tooltip"
            data-tooltip-template-id="preview-tooltip"
            data-tippy-maxWidth="none"
        >
            <a
                role="button"
                class="markdown_preview compose_control_button zulip-icon zulip-icon-preview"
                aria-label="${$t({defaultMessage: "Preview mode"})}"
                tabindex="0"
            ></a>
        </div>
        <div
            class="compose_control_button_container compose_button_tooltip"
            data-tooltip-template-id="exit-preview-tooltip"
            data-tippy-maxWidth="none"
        >
            <a
                role="button"
                class="undo_markdown_preview compose_control_button zulip-icon zulip-icon-compose-edit"
                aria-label="${$t({defaultMessage: "Exit preview mode"})}"
                tabindex="0"
                style="display:none;"
            ></a>
        </div>
        ${to_bool(context.file_upload_enabled)
            ? html`
                  <div
                      class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
                      data-tippy-content="${$t({defaultMessage: "Upload files"})}"
                  >
                      <a
                          role="button"
                          class="compose_control_button compose_upload_file zulip-icon zulip-icon-attachment"
                          aria-label="${$t({defaultMessage: "Upload files"})}"
                          tabindex="0"
                      ></a>
                  </div>
              `
            : ""}
        <div
            class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
            data-tippy-content="${$t({defaultMessage: "Add video call"})}"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-video-call video_link"
                aria-label="${$t({defaultMessage: "Add video call"})}"
                tabindex="0"
            ></a>
        </div>
        <div
            class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
            data-tippy-content="${$t({defaultMessage: "Add voice call"})}"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-voice-call audio_link"
                aria-label="${$t({defaultMessage: "Add voice call"})}"
                tabindex="0"
            ></a>
        </div>
        <div class="divider"></div>
        <div
            class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
            data-tippy-content="${$t({defaultMessage: "Add emoji"})}"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-smile-bigger emoji_map"
                aria-label="${$t({defaultMessage: "Add emoji"})}"
                tabindex="0"
            ></a>
        </div>
        <div
            class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
            data-tooltip-template-id="add-global-time-tooltip"
            data-tippy-maxWidth="none"
        >
            <a
                role="button"
                class="compose_control_button zulip-icon zulip-icon-time time_pick"
                aria-label="${$t({defaultMessage: "Add global time"})}"
                tabindex="0"
            ></a>
        </div>
        ${to_bool(context.tenor_enabled) || to_bool(context.giphy_enabled)
            ? /* We prefer showing the Tenor picker over the GIPHY picker, if both are enabled. */ html`
                  <div
                      class="compose_control_button_container  preview_mode_disabled compose_button_tooltip"
                      data-tippy-content="${$t({defaultMessage: "Add GIF"})}"
                  >
                      <a
                          role="button"
                          class="compose_control_button ${to_bool(context.tenor_enabled)
                              ? "compose-gif-icon-tenor"
                              : "compose-gif-icon-giphy"} zulip-icon zulip-icon-gif"
                          aria-label="${$t({defaultMessage: "Add GIF"})}"
                          tabindex="0"
                      ></a>
                  </div>
              `
            : ""}${to_bool(context.message_id)
            ? html`
                  <div
                      class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
                      data-tooltip-template-id="add-saved-snippet-tooltip"
                  >
                      <a
                          role="button"
                          class="saved_snippets_widget saved-snippets-message-edit-widget compose_control_button zulip-icon zulip-icon-message-square-text"
                          aria-label="${$t({defaultMessage: "Add saved snippet"})}"
                          data-message-id="${context.message_id}"
                          tabindex="0"
                      ></a>
                  </div>
              `
            : html`
                  <div
                      class="compose_control_button_container preview_mode_disabled compose_button_tooltip"
                      data-tooltip-template-id="add-saved-snippet-tooltip"
                  >
                      <a
                          role="button"
                          class="saved_snippets_widget saved-snippets-composebox-widget compose_control_button zulip-icon zulip-icon-message-square-text"
                          aria-label="${$t({defaultMessage: "Add saved snippet"})}"
                          tabindex="0"
                      ></a>
                  </div>
              `}
        <div class="divider"></div>
        <div class="compose-control-buttons-container preview_mode_disabled">
            <a
                role="button"
                data-format-type="link"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-link formatting_button"
                aria-label="${$t({defaultMessage: "Link"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tooltip-template-id="link-tooltip"
                data-tippy-maxWidth="none"
            ></a>
            <a
                role="button"
                data-format-type="bold"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-bold formatting_button"
                aria-label="${$t({defaultMessage: "Bold"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tooltip-template-id="bold-tooltip"
                data-tippy-maxWidth="none"
            ></a>
            <a
                role="button"
                data-format-type="italic"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-italic formatting_button"
                aria-label="${$t({defaultMessage: "Italic"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tooltip-template-id="italic-tooltip"
                data-tippy-maxWidth="none"
            ></a>
            <a
                role="button"
                data-format-type="strikethrough"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-strikethrough formatting_button"
                aria-label="${$t({defaultMessage: "Strikethrough"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Strikethrough"})}"
            ></a>
        </div>
        <div class="divider"></div>
        <div class="compose-control-buttons-container preview_mode_disabled">
            <a
                role="button"
                data-format-type="numbered"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-ordered-list formatting_button"
                aria-label="${$t({defaultMessage: "Numbered list"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Numbered list"})}"
            ></a>
            <a
                role="button"
                data-format-type="bulleted"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-unordered-list formatting_button"
                aria-label="${$t({defaultMessage: "Bulleted list"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Bulleted list"})}"
            ></a>
            <div class="divider"></div>
            <a
                role="button"
                data-format-type="quote"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-quote formatting_button"
                aria-label="${$t({defaultMessage: "Quote"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Quote"})}"
            ></a>
            <a
                role="button"
                data-format-type="spoiler"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-spoiler formatting_button"
                aria-label="${$t({defaultMessage: "Spoiler"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Spoiler"})}"
            ></a>
            <a
                role="button"
                data-format-type="code"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-code formatting_button"
                aria-label="${$t({defaultMessage: "Code"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tooltip-template-id="code-tooltip"
            ></a>
            <a
                role="button"
                data-format-type="latex"
                class="compose_button_tooltip compose_control_button zulip-icon zulip-icon-math formatting_button"
                aria-label="${$t({defaultMessage: "Math (LaTeX)"})}"
                ${!to_bool(context.preview_mode_on) ? " tabindex=0 " : ""}
                data-tippy-content="${$t({defaultMessage: "Math (LaTeX)"})}"
            ></a>
        </div>
        <div class="divider"></div>
        ${!to_bool(context.message_id)
            ? html`
                  <div
                      class="compose_control_button_container preview_mode_disabled needs-empty-compose compose_button_tooltip"
                      data-tooltip-template-id="add-poll-tooltip"
                      data-tippy-maxWidth="none"
                  >
                      <a
                          role="button"
                          class="compose_control_button zulip-icon zulip-icon-poll add-poll"
                          aria-label="${$t({defaultMessage: "Add poll"})}"
                          tabindex="0"
                      ></a>
                  </div>
                  <div
                      class="compose_control_button_container preview_mode_disabled needs-empty-compose compose_button_tooltip"
                      data-tooltip-template-id="add-todo-tooltip"
                      data-tippy-maxWidth="none"
                  >
                      <a
                          role="button"
                          class="compose_control_button zulip-icon zulip-icon-todo-list add-todo-list"
                          aria-label="${$t({defaultMessage: "Add to-do list"})}"
                          tabindex="0"
                      ></a>
                  </div>
              `
            : ""}
        <a
            role="button"
            class="compose_control_button compose_help_button zulip-icon zulip-icon-question compose_button_tooltip"
            tabindex="0"
            data-tippy-content="${$t({defaultMessage: "Message formatting"})}"
            data-overlay-trigger="message-formatting"
        ></a>
    </div> `;
    return to_html(out);
}

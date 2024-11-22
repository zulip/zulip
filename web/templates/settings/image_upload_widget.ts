import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_image_upload_widget(context) {
    const out = html`<div
        id="${context.widget}-upload-widget"
        class="inline-block image_upload_widget"
    >
        ${to_bool(context.disabled_text)
            ? html`
                  <div
                      class="image-disabled ${to_bool(context.is_editable_by_current_user)
                          ? "hide"
                          : ""}"
                  >
                      <div class="image-hover-background"></div>
                      <span
                          class="image-disabled-text flex"
                          aria-label="${context.disabled_text}"
                          role="button"
                          tabindex="0"
                      >
                          ${context.disabled_text}
                      </span>
                  </div>
              `
            : ""}
        <div
            class="image_upload_button ${!to_bool(context.is_editable_by_current_user)
                ? "hide"
                : ""}"
        >
            <div class="image-hover-background"></div>
            <button
                class="image-delete-button"
                aria-label="${context.delete_text}"
                role="button"
                tabindex="0"
            >
                &times;
            </button>
            <span class="image-delete-text" aria-label="${context.delete_text}" tabindex="0">
                ${context.delete_text}
            </span>
            <span
                class="image-upload-text"
                aria-label="${context.upload_text}"
                role="button"
                tabindex="0"
            >
                ${context.upload_text}
            </span>
            <span class="upload-spinner-background">
                <img class="image_upload_spinner" src="../../images/loading/tail-spin.svg" alt="" />
            </span>
        </div>
        <img class="image-block" src="${context.image}" />
        <input
            type="file"
            name="file_input"
            class="notvisible image_file_input"
            value="${context.upload_text}"
        />
        <div class="image_file_input_error text-error"></div>
    </div> `;
    return to_html(out);
}

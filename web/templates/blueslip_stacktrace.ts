import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";

export default function render_blueslip_stacktrace(context) {
    const out = to_array(context.errors).map(
        (error, error_index) => html`
            <div class="stacktrace-header">
                <div class="warning-symbol">
                    <i class="fa fa-exclamation-triangle"></i>
                </div>
                <div class="message">
                    ${error_index !== 0 ? "caused by " : ""}<strong>${error.name}:</strong>
                    ${error.message}
                </div>
                ${error_index === 0 ? html` <div class="exit"></div> ` : ""}
            </div>
            ${to_bool(error.more_info)
                ? html` <div class="stacktrace-more-info">${error.more_info}</div> `
                : ""}
            <div class="stacktrace-content">
                ${to_array(error.stackframes).map(
                    (frame) => html`
                        <div
                            data-full-path="${frame.full_path}"
                            data-line-no="${frame.line_number}"
                        >
                            <div class="stackframe">
                                <i class="fa fa-caret-right expand"></i>
                                <span class="subtle">at</span>
                                ${to_bool(frame.function_name)
                                    ? html`
                                          ${frame.function_name.scope}<b
                                              >${frame.function_name.name}</b
                                          >
                                      `
                                    : ""}
                                <span class="subtle">${frame.show_path}:${frame.line_number}</span>
                            </div>
                            <div class="code-context" style="display: none">
                                <div class="code-context-content">
                                    ${to_array(frame.context).map(
                                        (context3) =>
                                            html`<div
                                                ${to_bool(context3.focus)
                                                    ? html`class="focus-line"`
                                                    : ""}
                                            >
                                                <span class="line-number"
                                                    >${context3.line_number}</span
                                                >
                                                ${context3.line}
                                            </div>`,
                                    )}
                                </div>
                            </div>
                        </div>
                    `,
                )}
            </div>
        `,
    );
    return to_html(out);
}

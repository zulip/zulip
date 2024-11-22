import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";

export default function render_generate_integration_url_modal(context) {
    const out = html`<div class="input-group">
            <div class="integration-url-name-wrapper integration-url-parameter">
                ${{
                    __html: render_dropdown_widget_with_label({
                        label: $t({defaultMessage: "Integration"}),
                        widget_name: "integration-name",
                    }),
                }}
            </div>
        </div>
        <div class="input-group">
            <div class="integration-url-stream-wrapper integration-url-parameter">
                ${{
                    __html: render_dropdown_widget_with_label({
                        label: $t({defaultMessage: "Where to send notifications"}),
                        widget_name: "integration-url-stream",
                    }),
                }}
            </div>
        </div>
        <div class="input-group control-label-disabled">
            <label class="checkbox">
                <input
                    type="checkbox"
                    id="integration-url-override-topic"
                    class="integration-url-parameter"
                    disabled
                />
                <span class="rendered-checkbox"></span>
            </label>
            <label class="inline" for="integration-url-override-topic">
                ${$t({defaultMessage: "Send all notifications to a single topic"})}
            </label>
        </div>
        <div class="input-group hide">
            <label for="integration-url-topic-input" class="modal-label-field"
                >${$t({defaultMessage: "Topic"})}</label
            >
            <input
                type="text"
                id="integration-url-topic-input"
                class="modal_text_input integration-url-parameter"
                maxlength="${context.max_topic_length}"
            />
        </div>
        <div id="integration-url-config-options-container">
            <!-- Dynamic Config Options will be rendered here -->
        </div>
        <div id="integration-events-parameter" class="input-group hide">
            <label class="checkbox">
                <input type="checkbox" id="show-integration-events" />
                <span class="rendered-checkbox"></span>
            </label>
            <label class="inline" for="show-integration-events">
                ${$t({defaultMessage: "Filter events that will trigger notifications?"})}
            </label>
        </div>
        <div class="input-group hide" id="integrations-event-container">
            <label for="integrations-event-options"
                >${$t({defaultMessage: "Events to include:"})}</label
            >
            <div class="integration-all-events-buttons">
                <button class="button rounded" id="add-all-integration-events">
                    ${$t({defaultMessage: "Check all"})}
                </button>
                <button class="button rounded" id="remove-all-integration-events">
                    ${$t({defaultMessage: "Uncheck all"})}
                </button>
            </div>
            <div id="integrations-event-options"></div>
        </div>
        <hr />
        <p class="integration-url-header">${$t({defaultMessage: "URL for your integration"})}</p>
        <div class="integration-url">${context.default_url_message}</div> `;
    return to_html(out);
}

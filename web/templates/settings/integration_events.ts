import {to_array} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_integration_events(context) {
    const out = to_array(context.events).map(
        (event) => html`
            <div class="integration-event-wrapper">
                <label class="checkbox">
                    <input
                        type="checkbox"
                        class="integration-event"
                        id="${event.event_id}"
                        checked="true"
                        value="${event.event}"
                    />
                    <span class="rendered-checkbox"></span>
                </label>
                <label for="${event.event_id}" class="inline integration-event-name">
                    ${event.event}
                </label>
            </div>
        `,
    );
    return to_html(out);
}

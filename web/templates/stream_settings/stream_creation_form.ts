import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_stream_types from "./stream_types.ts";

export default function render_stream_creation_form(context) {
    const out = html`<div
        class="hide"
        id="stream-creation"
        tabindex="-1"
        role="dialog"
        aria-label="${$t({defaultMessage: "Channel creation"})}"
    >
        <form id="stream_creation_form">
            <div
                class="stream-creation-simplebar-container"
                data-simplebar
                data-simplebar-tab-index="-1"
            >
                <div class="alert stream_create_info"></div>
                <div id="stream_creating_indicator"></div>
                <div class="stream-creation-body">
                    <div class="configure_channel_settings stream_creation_container">
                        <section id="create_stream_title_container">
                            <label for="create_stream_name">
                                ${$t({defaultMessage: "Channel name"})}
                            </label>
                            <input
                                type="text"
                                name="stream_name"
                                id="create_stream_name"
                                class="settings_text_input"
                                placeholder="${$t({defaultMessage: "Channel name"})}"
                                value=""
                                autocomplete="off"
                                maxlength="${context.max_stream_name_length}"
                            />
                            <div id="stream_name_error" class="stream_creation_error"></div>
                            <a id="archived_stream_rename"></a>
                        </section>
                        <section id="create_stream_description_container">
                            <label for="create_stream_description" class="settings-field-label">
                                ${$t({defaultMessage: "Channel description"})}
                                ${{
                                    __html: render_help_link_widget({
                                        link: "/help/change-the-channel-description",
                                    }),
                                }}
                            </label>
                            <input
                                type="text"
                                name="stream_description"
                                id="create_stream_description"
                                class="settings_text_input"
                                placeholder="${$t({defaultMessage: "Channel description"})}"
                                value=""
                                autocomplete="off"
                                maxlength="${context.max_stream_description_length}"
                            />
                        </section>
                        <section id="make-invite-only">
                            <div class="stream-types">
                                ${{
                                    __html: render_stream_types({
                                        prefix: "id_new_",
                                        is_stream_edit: false,
                                        stream_post_policy:
                                            context.stream_post_policy_values.everyone.code,
                                        ...context,
                                    }),
                                }}
                            </div>
                        </section>
                    </div>
                    <div class="subscribers_container stream_creation_container">
                        <section class="stream_create_add_subscriber_container">
                            <label class="choose-subscribers-label">
                                <h4 class="stream_setting_subsection_title">
                                    ${$t({defaultMessage: "Choose subscribers"})}
                                </h4>
                            </label>
                            <span class="add_all_users_to_stream_button_container">
                                <button
                                    class="add_all_users_to_stream small button rounded sea-green"
                                >
                                    ${$t({defaultMessage: "Add all users"})}
                                </button>
                            </span>
                            <div id="stream_subscription_error" class="stream_creation_error"></div>
                            <div class="controls" id="people_to_add"></div>
                        </section>
                    </div>
                </div>
            </div>
            <div class="settings-sticky-footer">
                <div class="settings-sticky-footer-left">
                    <button
                        id="stream_creation_go_to_configure_channel_settings"
                        class="button small sea-green rounded hide"
                    >
                        ${$t({defaultMessage: "Back to settings"})}
                    </button>
                </div>
                <div class="settings-sticky-footer-right">
                    <button
                        class="create_stream_cancel button small white rounded"
                        data-dismiss="modal"
                    >
                        ${$t({defaultMessage: "Cancel"})}
                    </button>
                    <button
                        class="finalize_create_stream button small sea-green rounded hide"
                        type="submit"
                    >
                        ${$t({defaultMessage: "Create"})}
                    </button>
                    <button
                        id="stream_creation_go_to_subscribers"
                        class="button small sea-green rounded"
                    >
                        ${$t({defaultMessage: "Continue to add subscribers"})}
                    </button>
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}

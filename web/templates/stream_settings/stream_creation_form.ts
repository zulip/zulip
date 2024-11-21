import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_new_stream_configuration from "./new_stream_configuration.ts";

export default function render_stream_creation_form(context) {
    const out = html`<div
        class="hide two-pane-settings-right-simplebar-container"
        id="stream-creation"
        tabindex="-1"
        role="dialog"
        aria-label="${$t({defaultMessage: "Channel creation"})}"
    >
        <form id="stream_creation_form">
            <div
                class="two-pane-settings-creation-simplebar-container"
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
                            <div class="new-stream-configuration">
                                ${{
                                    __html: render_new_stream_configuration({
                                        channel_folder_widget_name: "new_channel_folder_id",
                                        prefix: "id_new_",
                                        ...context,
                                    }),
                                }}
                            </div>
                        </section>
                    </div>
                    <div class="subscribers_container stream_creation_container">
                        <section class="stream_create_add_subscriber_container">
                            <h4 class="stream_setting_subsection_title">
                                <label class="choose-subscribers-label"
                                    >${$t({defaultMessage: "Choose subscribers"})}</label
                                >
                            </h4>
                            <div id="stream_subscription_error" class="stream_creation_error"></div>
                            <div class="controls" id="people_to_add"></div>
                        </section>
                    </div>
                </div>
            </div>
            <div class="settings-sticky-footer">
                <div class="settings-sticky-footer-left">
                    ${{
                        __html: render_action_button({
                            intent: "brand",
                            attention: "quiet",
                            id: "stream_creation_go_to_configure_channel_settings",
                            custom_classes: "hide",
                            label: $t({defaultMessage: "Back to settings"}),
                        }),
                    }}
                </div>
                <div class="settings-sticky-footer-right">
                    ${{
                        __html: render_action_button({
                            intent: "neutral",
                            attention: "quiet",
                            custom_classes: "create_stream_cancel inline-block",
                            label: $t({defaultMessage: "Cancel"}),
                        }),
                    }}
                    ${{
                        __html: render_action_button({
                            type: "submit",
                            intent: "brand",
                            attention: "quiet",
                            custom_classes: "finalize_create_stream hide",
                            label: $t({defaultMessage: "Create"}),
                        }),
                    }}
                    ${{
                        __html: render_action_button({
                            intent: "brand",
                            attention: "quiet",
                            id: "stream_creation_go_to_subscribers",
                            custom_classes: "inline-block",
                            label: $t({defaultMessage: "Continue to add subscribers"}),
                        }),
                    }}
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}

import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_buddy_list_title_tooltip from "../templates/buddy_list/title_tooltip.hbs";
import render_change_visibility_policy_button_tooltip from "../templates/change_visibility_policy_button_tooltip.hbs";
import render_information_density_update_button_tooltip from "../templates/information_density_update_button_tooltip.hbs";
import render_org_logo_tooltip from "../templates/org_logo_tooltip.hbs";
import render_tooltip_templates from "../templates/tooltip_templates.hbs";
import render_topics_not_allowed_error from "../templates/topics_not_allowed_error.hbs";

import * as compose_validate from "./compose_validate.ts";
import {$t} from "./i18n.ts";
import * as information_density from "./information_density.ts";
import * as people from "./people.ts";
import * as settings_config from "./settings_config.ts";
import * as stream_data from "./stream_data.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

// For tooltips without data-tippy-content, we use the HTML content of
// a <template> whose id is given by data-tooltip-template-id.
export function get_tooltip_content(reference: Element): string | Element | DocumentFragment {
    if (reference instanceof HTMLElement && reference.dataset.tooltipTemplateId !== undefined) {
        const template = document.querySelector<HTMLTemplateElement>(
            `template#${CSS.escape(reference.dataset.tooltipTemplateId)}`,
        );
        if (template !== null) {
            const fragment = template.content.cloneNode(true);
            assert(fragment instanceof DocumentFragment);
            return fragment;
        }
    }
    return "";
}

// We use different delay settings for tooltips. The default "instant"
// version has just a tiny bit of delay to create a natural feeling
// transition, while the "long" version is intended for elements where
// we want to avoid distracting the user with the tooltip
// unnecessarily.
export const INSTANT_HOVER_DELAY: [number, number] = [100, 20];
// INTERACTIVE_HOVER_DELAY is for elements like the emoji reactions, where
// the tooltip includes useful information (who reacted?), but that
// needs a short delay for users who are just tapping a reaction
// element and not interested in the tooltip's contents.
export const INTERACTIVE_HOVER_DELAY: [number, number] = [425, 20];
export const LONG_HOVER_DELAY: [number, number] = [750, 20];
// EXTRA_LONG_HOVER_DELAY is for elements like the compose box send
// button where the tooltip content is almost exactly the same as the
// text in the button, and the tooltip exists just to advertise a
// keyboard shortcut. For these tooltips, it's very important to avoid
// distracting users unnecessarily.
export const EXTRA_LONG_HOVER_DELAY: [number, number] = [1500, 20];

// We override the defaults set by tippy library here,
// so make sure to check this too after checking tippyjs
// documentation for default properties.
tippy.default.setDefaultProps({
    // Tooltips shouldn't take more space than mobile widths.
    // 300px at 14px/1em
    maxWidth: "21.4286em",
    delay: INSTANT_HOVER_DELAY,
    placement: "top",
    // Disable animations to make the tooltips feel snappy.
    animation: false,
    // Show tooltips on long press on touch based devices.
    touch: ["hold", 750],
    // Create the tooltip inside the parent element. This has the
    // undesirable side effect of CSS properties of the parent elements
    // applying to tooltips, which causes ugly clipping if the parent
    // element has overflow rules. Even with that, we prefer to have
    // tooltips appended to the parent so that the tooltip gets removed
    // if the parent is hidden / removed from DOM; which is not the case
    // with appending it to `body` which has side effect of tooltips
    // sticking around due to browser not communicating to tippy that
    // the element has been removed without having a Mutation Observer.
    appendTo: "parent",
    // To add a text tooltip, override this by setting data-tippy-content.
    // To add an HTML tooltip, set data-tooltip-template-id to the id of a <template>.
    // Or, override this with a function returning string (text) or DocumentFragment (HTML).
    content: get_tooltip_content,
});

export const topic_visibility_policy_tooltip_props = {
    delay: LONG_HOVER_DELAY,
    appendTo: () => document.body,
    onShow(instance: tippy.Instance) {
        const $elem = $(instance.reference);
        let should_render_privacy_icon;
        let current_visibility_policy_str;
        if ($elem.hasClass("zulip-icon-inherit")) {
            should_render_privacy_icon = true;
        } else {
            should_render_privacy_icon = false;
            current_visibility_policy_str = $elem.attr("data-tippy-content");
        }
        let current_stream_obj;
        if (should_render_privacy_icon) {
            current_stream_obj = stream_data.get_sub_by_id(
                Number($elem.parent().attr("data-stream-id")),
            );
        }
        const tooltip_context = {
            ...current_stream_obj,
            current_visibility_policy_str,
            should_render_privacy_icon,
        };
        instance.setContent(
            ui_util.parse_html(render_change_visibility_policy_button_tooltip(tooltip_context)),
        );
    },
    onHidden(instance: tippy.Instance) {
        instance.destroy();
    },
};

export function initialize(): void {
    $("#tooltip-templates-container").html(render_tooltip_templates());

    // Our default tooltip configuration. For this, one simply needs to:
    // * Set `class="tippy-zulip-tooltip"` on an element for enable this.
    // * Set `data-tippy-content="{{t 'Tooltip content' }}"`, often
    //   replacing a `title` attribute on an element that had both.
    // * Set placement; we typically use `data-tippy-placement="top"`.
    tippy.delegate("body", {
        target: ".tippy-zulip-tooltip",
    });

    // variant of tippy-zulip-tooltip above having delay=LONG_HOVER_DELAY,
    // default placement="top" with fallback placement="bottom",
    // and appended to body
    tippy.delegate("body", {
        target: ".tippy-zulip-delayed-tooltip",
        // Disable trigger on focus, to avoid displaying on-click.
        trigger: "mouseenter",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        popperOptions: {
            modifiers: [
                {
                    name: "flip",
                    options: {
                        fallbackPlacements: "bottom",
                    },
                },
            ],
        },
    });

    tippy.delegate("body", {
        target: ".toggle-subscription-tooltip",
        trigger: "mouseenter",
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "bottom",
        onShow(instance) {
            let template = "show-unsubscribe-tooltip-template";
            if (instance.reference.classList.contains("unsubscribed")) {
                template = "show-subscribe-tooltip-template";
            }
            $(instance.reference).attr("data-tooltip-template-id", template);
            instance.setContent(get_tooltip_content(instance.reference));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#subscription_overlay .subscription_settings .sub-stream-name",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "top",
        onShow(instance) {
            const stream_name_element = instance.reference;
            assert(stream_name_element instanceof HTMLElement);
            // Only show tooltip if the stream name is truncated.
            // See https://stackoverflow.com/questions/21064101/understanding-offsetwidth-clientwidth-scrollwidth-and-height-respectively
            // for more details.
            if (stream_name_element.offsetWidth >= stream_name_element.scrollWidth) {
                return false;
            }

            return undefined;
        },
    });

    // The below definitions are for specific tooltips that require
    // custom JavaScript code or configuration.  Note that since the
    // below specify the target directly, elements using those should
    // not have the tippy-zulip-tooltip class.

    tippy.delegate("body", {
        target: ".draft-selection-tooltip",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onShow(instance) {
            let content = $t({defaultMessage: "Select draft"});
            const $elem = $(instance.reference);
            if ($($elem).parent().find(".draft-selection-checkbox").hasClass("fa-check-square")) {
                content = $t({defaultMessage: "Deselect draft"});
            }
            instance.setContent(content);
        },
    });

    tippy.delegate("body", {
        target: ".delete-selected-drafts-button-container",
        appendTo: () => document.body,
        onShow(instance) {
            let content = $t({defaultMessage: "Delete all selected drafts"});
            const $elem = $(instance.reference);
            if ($($elem).find(".delete-selected-drafts-button").is(":disabled")) {
                content = $t({defaultMessage: "No drafts selected"});
            }
            instance.setContent(content);
        },
    });

    tippy.delegate("body", {
        target: "#add-poll-modal .dialog_submit_button_container",
        appendTo: () => document.body,
        onShow(instance) {
            const content = $t({defaultMessage: "Please enter a question."});
            const $elem = $(instance.reference);
            // Show tooltip to enter question only if submit button is disabled
            // (due to question field being empty).
            if ($elem.find(".dialog_submit_button").is(":disabled")) {
                instance.setContent(content);
                return undefined;
            }
            return false;
        },
    });

    tippy.delegate("body", {
        target: "#add-todo-modal .todo-description-container",
        onShow(instance) {
            const $elem = $(instance.reference);

            /* Due to height: 0, data-reference-hidden for tooltip is set on the tooltip and can
            cause the tooltip to hide. We should  use .show-when-reference-hidden here too since we
            want data-reference-hidden to work when user scrolls here.*/
            $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");

            if ($elem.find(".todo-description-input").is(":disabled")) {
                instance.setContent(
                    $t({
                        defaultMessage: "Enter a task before adding a description.",
                    }),
                );
                return undefined;
            }
            return false;
        },
        appendTo: () => document.body,
    });

    $("body").on(
        "blur",
        ".message_control_button, .delete-selected-drafts-button-container",
        function (this: tippy.ReferenceElement, _event: JQuery.Event) {
            // Remove tooltip when user is trying to tab through all the icons.
            // If user tabs slowly, tooltips are displayed otherwise they are
            // destroyed before they can be displayed.
            this._tippy?.destroy();
        },
    );

    tippy.delegate("body", {
        target: [
            "#scroll-to-bottom-button-clickable-area",
            ".spectator_narrow_login_button",
            ".error-icon-message-recipient .zulip-icon",
            "#personal-menu-dropdown .status-circle",
            ".popover-group-menu-member-list .popover-group-menu-user-presence",
            "#copy_generated_invite_link",
            ".delete-code-playground",
        ].join(","),
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: [
            "#compose_close",
            ".expand-composebox-button",
            ".collapse-composebox-button",
            ".maximize-composebox-button",
        ].join(","),
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".media-info-wrapper > .media-description > .title",
        appendTo: () => document.body,
        onShow(instance) {
            const title = $(instance.reference).attr("aria-label");
            if (title === undefined) {
                return false;
            }
            const filename = $(instance.reference).attr("data-filename");
            const $markup = $("<span>").text(title);
            if (title !== filename) {
                // If the image title is the same as the filename, there's no reason
                // to show this next line.
                const second_line = $t({defaultMessage: "File name: {filename}"}, {filename});
                $markup.append($("<br>"), $("<span>").text(second_line));
            }
            instance.setContent(util.the($markup));
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        // Configure tooltips for the stream_sorter_toggle buttons.

        // TODO: Ideally, we'd extend this to be a common mechanism for
        // tab switchers, with the strings living in a more normal configuration
        // location.
        target: ".stream_sorter_toggle .ind-tab [data-tippy-content]",

        // Adjust their placement to `bottom`.
        placement: "bottom",

        // Avoid inheriting `position: relative` CSS on the stream sorter widget.
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        // This tooltip appears on the "Summary" checkboxes in
        // settings > custom profile fields, when at the limit of 2
        // fields with display_in_profile_summary enabled.
        target: [
            "#profile-field-settings .display_in_profile_summary_tooltip",
            "#edit-custom-profile-field-form-modal .display_in_profile_summary_tooltip",
            "#add-new-custom-profile-field-form .display_in_profile_summary_tooltip",
        ].join(","),
        content: $t({
            defaultMessage: "Only 2 custom profile fields can be displayed on the user card.",
        }),
        appendTo: () => document.body,
        onTrigger(instance) {
            // Sometimes just removing class is not enough to destroy/remove tooltip, especially in
            // "Add a new custom profile field" form, so here we are manually calling `destroy()`.
            if (!instance.reference.classList.contains("display_in_profile_summary_tooltip")) {
                instance.destroy();
            }
        },
    });

    tippy.delegate("body", {
        target: "#full_name_input_container.disabled_setting_tooltip",
        content: $t({
            defaultMessage:
                "Name changes are disabled in this organization. Contact an administrator to change your name.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#email_field_container.disabled_setting_tooltip",
        content: $t({defaultMessage: "Email address changes are disabled in this organization."}),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#deactivate_account_container.disabled_setting_tooltip",
        content: $t({
            defaultMessage:
                "Because you are the only organization owner, you cannot deactivate your account.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#deactivate_realm_button_container.disabled_setting_tooltip",
        content: $t({
            defaultMessage: "Only organization owners may deactivate an organization.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".settings-radio-input-parent.default_stream_private_tooltip",
        content: $t({
            defaultMessage: "Default channels for new users cannot be made private.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: [
            "[data-tab-key='not-subscribed'].disabled",
            "[data-tab-key='all-streams'].disabled",
        ].join(","),
        content: $t({
            defaultMessage: "You can only view channels that you are subscribed to.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".default-stream.default_stream_private_tooltip",
        content: $t({
            defaultMessage: "Private channels cannot be default channels for new users.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "[data-tab-key='invite-link-tab'].disabled",
        content: $t({
            defaultMessage:
                "You do not have permissions to create invite links in this organization.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: [
            "#user_email_address_dropdown_container.disabled_setting_tooltip",
            "#realm_invite_required_container.disabled_setting_tooltip",
        ].join(","),
        content: $t({
            defaultMessage: "Configure your email to access this feature.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#api_key_button_container.disabled_setting_tooltip",
        content: $t({
            defaultMessage: "Add an email to access your API key.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "[data-tab-key='invite-email-tab'].disabled",
        content: $t({
            defaultMessage:
                "You do not have permissions to send invite emails in this organization.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#user_message_content_in_email_notifications_label",
        onShow(instance) {
            if ($("#user_message_content_in_email_notifications").prop("disabled")) {
                instance.setContent(
                    $t({
                        defaultMessage:
                            "Including message content in message notification emails is not allowed in this organization.",
                    }),
                );
                return undefined;
            }
            instance.destroy();
            return false;
        },
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: "#stream_creation_form .add_subscribers_disabled",
        content: $t({
            defaultMessage:
                "You do not have permission to add other users to channels in this organization.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".add-users-button-wrapper",
        onShow(instance) {
            const $wrapper = $(instance.reference);
            const $button = $wrapper.find("button");
            const $container = $wrapper.closest(".add-button-container").find(".pill-container");

            const button_is_disabled = Boolean($button.prop("disabled"));
            const container_is_enabled =
                $container.find(".input").prop("contenteditable") === "true";

            if (button_is_disabled && container_is_enabled) {
                instance.setContent(
                    $t({
                        defaultMessage: "Enter who should be added.",
                    }),
                );
                return undefined;
            }

            return false;
        },
        appendTo: () => document.body,
        placement: "top",
        delay: INSTANT_HOVER_DELAY,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".user_row .actions button",
        trigger: "mouseenter",
        onShow(instance) {
            if ($(instance.reference).closest("span").hasClass("deactivate-user-tooltip")) {
                instance.setContent($t({defaultMessage: "Deactivate user"}));
                return undefined;
            } else if ($(instance.reference).closest("span").hasClass("reactivate-user-tooltip")) {
                instance.setContent($t({defaultMessage: "Reactivate user"}));
                return undefined;
            } else if ($(instance.reference).closest("span").hasClass("deactivate-bot-tooltip")) {
                instance.setContent($t({defaultMessage: "Deactivate bot"}));
                return undefined;
            } else if ($(instance.reference).closest("span").hasClass("reactivate-bot-tooltip")) {
                instance.setContent($t({defaultMessage: "Reactivate bot"}));
                return undefined;
            }
            return false;
        },
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: ".user-card-status-area .status-emoji",
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: ".status-emoji-name",
        placement: "top",
        delay: INSTANT_HOVER_DELAY,
        appendTo: () => document.body,

        /*
            Status emoji tooltips for most locations in the app. This
            basic tooltip logic is overridden by separate logic in
            click_handlers.ts for the left and right sidebars, to
            avoid problematic interactions with the main tooltips for
            those regions.
        */

        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: [
            ".custom-profile-field-value",
            ".copy-custom-profile-field-link",
            "#popover-menu-copy-email",
            ".personal-menu-clear-status",
            ".user-card-clear-status-button",
        ].join(","),
        placement: "top",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onHidden(instance: tippy.Instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        /*
            The tooltip for new user group button (+) icon button on #groups
            overlay was not mounted correctly as its sibling element (search bar)
            is inserted dynamically after handlebar got rendered. So we append the
            tooltip element to the body itself with target as the + button.
        */
        target: "#groups_overlay .two-pane-settings-plus-button",
        content: $t({
            defaultMessage: "Create new user group",
        }),
        placement: "bottom",
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: "#move_topic_to_stream_widget_wrapper",
        onShow(instance) {
            if ($("#move_topic_to_stream_widget").prop("disabled")) {
                instance.setContent(
                    $t({
                        defaultMessage:
                            "You do not have permission to move messages to another channel in this organization.",
                    }),
                );
                return undefined;
            }
            return false;
        },
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: "#userlist-header-search",
        delay: LONG_HOVER_DELAY,
        placement: "top",
        appendTo: () => document.body,
        onShow(instance) {
            const total_user_count = people.get_active_human_count();
            instance.setContent(
                ui_util.parse_html(render_buddy_list_title_tooltip({total_user_count})),
            );
        },
    });

    tippy.delegate("body", {
        target: "#userlist-toggle-button",
        delay: LONG_HOVER_DELAY,
        placement: "bottom",
        appendTo: () => document.body,
        onShow(instance) {
            let template = "show-userlist-tooltip-template";
            if ($("#right-sidebar-container").css("display") !== "none") {
                template = "hide-userlist-tooltip-template";
            }
            $(instance.reference).attr("data-tooltip-template-id", template);
            instance.setContent(get_tooltip_content(instance.reference));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#realm-navbar-wide-logo",
        placement: "right",
        appendTo: () => document.body,
        onShow(instance) {
            const escape_navigates_to_home_view = user_settings.web_escape_navigates_to_home_view;
            const home_view =
                settings_config.web_home_view_values[user_settings.web_home_view].description;
            instance.setContent(
                ui_util.parse_html(
                    render_org_logo_tooltip({home_view, escape_navigates_to_home_view}),
                ),
            );
        },
    });

    tippy.delegate("body", {
        target: ".custom-user-field-label-wrapper.required-field-wrapper",
        content: $t({
            defaultMessage: "This profile field is required.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".settings-profile-user-field.not-editable-by-user-input-wrapper",
        content: $t({
            defaultMessage:
                "You are not allowed to change this field. Contact an administrator to update it.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".popover-contains-shift-hotkey",
        trigger: "mouseenter",
        placement: "top",
        appendTo: () => document.body,
        onShow(instance) {
            const hotkey_hints = $(instance.reference).attr("data-hotkey-hints");
            if (hotkey_hints) {
                instance.setContent(hotkey_hints.replace("⇧", "Shift").replaceAll(",", " + "));
                return undefined;
            }
            return false;
        },
    });

    tippy.delegate("body", {
        target: ".saved_snippets-dropdown-list-container .dropdown-list-delete",
        content: $t({defaultMessage: "Delete snippet"}),
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".saved_snippets-dropdown-list-container .dropdown-list-edit",
        content: $t({defaultMessage: "Edit snippet"}),
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".generate-channel-email-button-container.disabled_setting_tooltip",
        onShow(instance) {
            instance.setContent(
                ui_util.parse_html(
                    $("#compose_disable_stream_reply_button_tooltip_template").html(),
                ),
            );
        },
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".disabled-tooltip",
        trigger: "focus mouseenter",
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".delete-option",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "top",
        onShow(instance) {
            /* Ensure the tooltip remains visible even when data-reference-hidden is set. */
            $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");

            instance.setContent($t({defaultMessage: "Delete"}));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: [
            "#personal-menu-dropdown .info-density-button-container",
            "#user-preferences .info-density-button-container",
            "#realm-user-default-settings .information-density-settings:not(.disabled-setting) .info-density-button-container",
            "#gear-menu-dropdown .info-density-button-container",
        ].join(","),
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "bottom",
        onShow(instance) {
            const button_container = instance.reference;
            assert(button_container instanceof HTMLElement);

            const tooltip_context =
                information_density.get_tooltip_context_for_info_density_buttons(
                    $(button_container).find(".info-density-button"),
                );
            instance.setContent(
                ui_util.parse_html(
                    render_information_density_update_button_tooltip(tooltip_context),
                ),
            );
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".topic-edit-save-wrapper",
        onShow(instance) {
            const $elem = $(instance.reference);
            if ($($elem).find(".topic_edit_save").prop("disabled")) {
                const error_message = compose_validate.get_topics_required_error_message_html();
                instance.setContent(ui_util.parse_html(error_message));
                // `display: flex` doesn't show the tooltip content inline when <i>general chat</i>
                // is in the error message.
                $(instance.popper).find(".tippy-content").css("display", "block");
                return undefined;
            }
            instance.destroy();
            return false;
        },
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#compose_recipient_box",
        delay: LONG_HOVER_DELAY,
        onShow(instance) {
            const $elem = $(instance.reference);
            if ($($elem).find("#stream_message_recipient_topic").prop("disabled")) {
                const error_message = render_topics_not_allowed_error({
                    empty_string_topic_display_name: util.get_final_topic_display_name(""),
                });
                instance.setContent(ui_util.parse_html(error_message));
                // `display: flex` doesn't show the tooltip content inline when <i>general chat</i>
                // is in the error message.
                $(instance.popper).find(".tippy-content").css("display", "block");
                return undefined;
            }
            instance.destroy();
            return false;
        },
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#move-topic-new-topic-input-wrapper",
        delay: LONG_HOVER_DELAY,
        onShow(instance) {
            const $elem = $(instance.reference);
            if ($($elem).find(".topics-disabled-channel").prop("disabled")) {
                const error_message = render_topics_not_allowed_error({
                    empty_string_topic_display_name: util.get_final_topic_display_name(""),
                });
                instance.setContent(ui_util.parse_html(error_message));
                // `display: flex` doesn't show the tooltip content inline when <i>general chat</i>
                // is in the error message.
                $(instance.popper).find(".tippy-content").css("display", "block");
                return undefined;
            }
            instance.destroy();
            return false;
        },
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });
}

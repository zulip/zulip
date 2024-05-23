import $ from "jquery";
import assert from "minimalistic-assert";
import type {ReferenceElement} from "tippy.js";
import tippy, {delegate} from "tippy.js";

import render_buddy_list_title_tooltip from "../templates/buddy_list/title_tooltip.hbs";
import render_org_logo_tooltip from "../templates/org_logo_tooltip.hbs";
import render_tooltip_templates from "../templates/tooltip_templates.hbs";

import {$t} from "./i18n";
import * as people from "./people";
import * as popovers from "./popovers";
import * as settings_config from "./settings_config";
import * as ui_util from "./ui_util";
import {user_settings} from "./user_settings";

// For tooltips without data-tippy-content, we use the HTML content of
// a <template> whose id is given by data-tooltip-template-id.
function get_tooltip_content(reference: Element): string | Element | DocumentFragment {
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
tippy.setDefaultProps({
    // Tooltips shouldn't take more space than mobile widths.
    maxWidth: 300,
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

export function initialize(): void {
    $("#tooltip-templates-container").html(render_tooltip_templates());

    // Our default tooltip configuration. For this, one simply needs to:
    // * Set `class="tippy-zulip-tooltip"` on an element for enable this.
    // * Set `data-tippy-content="{{t 'Tooltip content' }}"`, often
    //   replacing a `title` attribute on an element that had both.
    // * Set placement; we typically use `data-tippy-placement="top"`.
    delegate("body", {
        target: ".tippy-zulip-tooltip",
    });

    // variant of tippy-zulip-tooltip above having delay=LONG_HOVER_DELAY,
    // default placement="top" with fallback placement="bottom",
    // and appended to body
    delegate("body", {
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

    delegate("body", {
        target: ".toggle-subscription-tooltip",
        trigger: "mouseenter",
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        placement: "bottom",
    });

    delegate("body", {
        target: ".tippy-left-sidebar-tooltip",
        placement: "right",
        delay: EXTRA_LONG_HOVER_DELAY,
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

    // Variant of .tippy-left-sidebar-tooltip configuration. Since
    // this element doesn't have an always visible label, and
    // thus hovering it is a way to find out what it does, give
    // it the faster LONG_HOVER_DELAY.
    delegate("body", {
        target: "#show_all_private_messages",
        placement: "right",
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

    // Variant of .tippy-left-sidebar-tooltip configuration. Here
    // we need to dynamically check which view is the home view.
    delegate("body", {
        target: ".tippy-views-tooltip",
        placement: "right",
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onShow(instance) {
            const $container = $(instance.popper).find(".views-tooltip-container");
            if ($container.data("view-code") === user_settings.web_home_view) {
                $container.find(".views-tooltip-home-view-note").removeClass("hide");
            }
        },
        onHidden(instance) {
            instance.destroy();
        },
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

    // The below definitions are for specific tooltips that require
    // custom JavaScript code or configuration.  Note that since the
    // below specify the target directly, elements using those should
    // not have the tippy-zulip-tooltip class.

    delegate("body", {
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

    delegate("body", {
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

    delegate("body", {
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

    $("body").on(
        "blur",
        ".message_control_button, .delete-selected-drafts-button-container",
        function (this: ReferenceElement) {
            // Remove tooltip when user is trying to tab through all the icons.
            // If user tabs slowly, tooltips are displayed otherwise they are
            // destroyed before they can be displayed.
            this._tippy?.destroy();
        },
    );

    delegate("body", {
        target: [
            "#streams_header .streams-tooltip-target",
            "#scroll-to-bottom-button-clickable-area",
            ".spectator_narrow_login_button",
            "#stream-specific-notify-table .unmute_stream",
            "#add_streams_tooltip",
            "#filter_streams_tooltip",
            ".error-icon-message-recipient .zulip-icon",
            "#personal-menu-dropdown .status-circle",
            "#copy_generated_invite_link",
        ].join(","),
        appendTo: () => document.body,
    });

    delegate("body", {
        target: [
            "#compose_top_right [data-tippy-content]",
            "#compose_top_right [data-tooltip-template-id]",
        ].join(","),
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
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
            instance.setContent($markup[0]);
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
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

    delegate("body", {
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

    delegate("body", {
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

    delegate("body", {
        target: "#change_email_button_container.disabled_setting_tooltip",
        content: $t({defaultMessage: "Email address changes are disabled in this organization."}),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: [
            "#deactivate_account_container.disabled_setting_tooltip",
            "#edit-user-form .deactivate_user_button_tooltip",
        ].join(","),
        content: $t({
            defaultMessage:
                "Because you are the only organization owner, you cannot deactivate your account.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: "#deactivate_realm_button_container.disabled_setting_tooltip",
        content: $t({
            defaultMessage: "Only organization owners may deactivate an organization.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: ".settings-radio-input-parent.default_stream_private_tooltip",
        content: $t({
            defaultMessage: "Default channels for new users cannot be made private.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: ".default-stream.default_stream_private_tooltip",
        content: $t({
            defaultMessage: "Private channels cannot be default channels for new users.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
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

    delegate("body", {
        target: [
            "#api_key_button_container.disabled_setting_tooltip",
            "#user_email_address_dropdown_container.disabled_setting_tooltip",
        ].join(","),
        content: $t({
            defaultMessage: "You must configure your email to access this feature.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
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

    delegate("body", {
        target: ".views-tooltip-target",
        onShow(instance) {
            if ($("#toggle-top-left-navigation-area-icon").hasClass("fa-caret-down")) {
                instance.setContent(
                    $t({
                        defaultMessage: "Collapse views",
                    }),
                );
            } else {
                instance.setContent($t({defaultMessage: "Expand views"}));
            }
        },
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
    });

    delegate("body", {
        target: ".dm-tooltip-target",
        onShow(instance) {
            if ($(".direct-messages-container").hasClass("zoom-in")) {
                return false;
            }

            if ($("#toggle_private_messages_section_icon").hasClass("fa-caret-down")) {
                instance.setContent(
                    $t({
                        defaultMessage: "Collapse direct messages",
                    }),
                );
            } else {
                instance.setContent($t({defaultMessage: "Expand direct messages"}));
            }
            return undefined;
        },
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
    });

    delegate("body", {
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

    delegate("body", {
        target: ".user_row .actions button",
        trigger: "mouseenter",
        onShow(instance) {
            if ($(instance.reference).hasClass("deactivate")) {
                instance.setContent($t({defaultMessage: "Deactivate"}));
                return undefined;
            } else if ($(instance.reference).hasClass("reactivate")) {
                instance.setContent($t({defaultMessage: "Reactivate"}));
                return undefined;
            }
            return false;
        },
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
    });

    delegate("body", {
        target: ".user-card-status-area .status-emoji",
        appendTo: () => document.body,
    });

    delegate("body", {
        target: ".status-emoji-name",
        placement: "top",
        delay: INSTANT_HOVER_DELAY,
        appendTo: () => document.body,

        /*
            Status emoji tooltips for most locations in the app. This
            basic tooltip logic is overridden by separate logic in
            click_handlers.js for the left and right sidebars, to
            avoid problematic interactions with the main tooltips for
            those regions.
        */

        onShow() {
            popovers.hide_all();
        },

        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        /*
            The tooltip for new user group button (+) icon button on #groups
            overlay was not mounted correctly as its sibling element (search bar)
            is inserted dynamically after handlebar got rendered. So we append the
            tooltip element to the body itself with target as the + button.
        */
        target: "#groups_overlay .create_user_group_plus_button",
        content: $t({
            defaultMessage: "Create new user group",
        }),
        placement: "bottom",
        appendTo: () => document.body,
    });

    delegate("body", {
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

    delegate("body", {
        target: "#userlist-header",
        placement: "top",
        appendTo: () => document.body,
        onShow(instance) {
            const total_user_count = people.get_active_human_count();
            instance.setContent(
                ui_util.parse_html(render_buddy_list_title_tooltip({total_user_count})),
            );
        },
    });

    delegate("body", {
        target: "#userlist-toggle",
        delay: LONG_HOVER_DELAY,
        placement: "bottom",
        appendTo: () => document.body,
        onShow(instance) {
            let template = "show-userlist-tooltip-template";
            if ($("#right-sidebar-container").is(":visible")) {
                template = "hide-userlist-tooltip-template";
            }
            $(instance.reference).attr("data-tooltip-template-id", template);
            instance.setContent(get_tooltip_content(instance.reference));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: "#realm-logo",
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

    delegate("body", {
        target: ".custom-user-field-label-wrapper.required-field-wrapper",
        content: $t({
            defaultMessage: "This profile field is required.",
        }),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
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
}

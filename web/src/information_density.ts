import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import {$t} from "./i18n.ts";
import * as resize from "./resize.ts";
import {stringify_time} from "./timerender.ts";
import {user_settings} from "./user_settings.ts";

// These are all relative-unit values for Source Sans Pro VF,
// as opened and inspected in FontForge.
// Source Sans Prof VF reports an em size of 1000, which is
// necessary to know to calculate proper em units.
const BODY_FONT_EM_SIZE = 1000;
// The Typo Ascent Value is reported as 1024, but both Chrome
// and Firefox act as though it is 1025, so that value is used
// here. It represents the portion of the content box above the
// baseline.
const BODY_FONT_ASCENT = 1025;
// The Typo Descent Value is reported as 400. It is the portion
// of the content box below the baseline.
const BODY_FONT_DESCENT = 400;
// The BODY_FONT_CONTENT_BOX size is calculated by adding the
// Typo Ascent and Typo Descent values. The content box for
// Source Sans Pro VF exceeds the size of its em box, meaning
// that the `font-size` value will render text that is smaller
// than the size of the content area. For example, setting
// `font-size: 100px` on Source Sans Prof VF produces a content
// area of 142.5px.
// Note also that the content box is therefore clipped when the
// line-height (in ems or as a unitless value) is less than the
// MAXIMUM_BLOCK_HEIGHT_IN_EMS as calculated below.
const BODY_FONT_CONTENT_BOX = BODY_FONT_ASCENT + BODY_FONT_DESCENT;
// The maximum block height is derived from the content area
// made by an anonymous text node in Source Sans Pro VF.
// This ensures that even as line heights scale above 1.425,
// text-adjacent elements can be sized in scale to the text's
// content area. This is necessary to know, because an element
// such as a checkbox or emoji looks nice occupying the full
// line-height, but only when the text's content area is less
// than the line-height.
const MAXIMUM_BLOCK_HEIGHT_IN_EMS = BODY_FONT_CONTENT_BOX / BODY_FONT_EM_SIZE;

export const NON_COMPACT_MODE_FONT_SIZE_PX = 16;
export const NON_COMPACT_MODE_LINE_HEIGHT_PERCENT = 140;

export const INFO_DENSITY_VALUES_DICT = {
    web_font_size_px: {
        default: NON_COMPACT_MODE_FONT_SIZE_PX,
        minimum: 12,
        maximum: 20,
        // by how much the value will be changed on clicking +/- buttons.
        step_value: 1,
    },
    web_line_height_percent: {
        default: NON_COMPACT_MODE_LINE_HEIGHT_PERCENT,
        minimum: 122,
        maximum: 158,
        // by how much the value will be changed on clicking +/- buttons.
        step_value: 9,
    },
};

// TODO: Compute these from INFO_DENSITY_VALUES_DICT, rather than repeating it.
const line_height_supported_values = [122, 131, 140, 149, 158];

export const MIN_VALUES = {
    web_font_size_px: 12,
    web_line_height_percent: 122,
};
export const MAX_VALUES = {
    web_font_size_px: 20,
    web_line_height_percent: 158,
};

function set_vertical_alignment_values(line_height_unitless: number): void {
    // We work in ems to keep this agnostic to the font size.
    const line_height_in_ems = line_height_unitless;
    const text_content_box_height_in_ems = MAXIMUM_BLOCK_HEIGHT_IN_EMS;
    // We calculate the descent area according to the BODY_FONT values. However,
    // to make that em value relative to the size of the content box, we need
    // to multiply that by the maximum block height, which is the content
    // box's em square (versus the em square of the value set on `font-size`).
    const descent_area_in_ems =
        (BODY_FONT_DESCENT / BODY_FONT_CONTENT_BOX) * MAXIMUM_BLOCK_HEIGHT_IN_EMS;

    // The height of line-fitted elements, such as inline emoji, is the
    // lesser of either the line height or the height of the adjacent
    // text content box.
    const line_fitted_height_in_ems = Math.min(line_height_in_ems, text_content_box_height_in_ems);

    // We obtain the correct vertical offset by taking the negative value
    // of the descent area, and adding it to half any non-zero difference
    // between the content box and the fitted line height.
    const line_fitted_vertical_align_offset_in_ems =
        -descent_area_in_ems + (text_content_box_height_in_ems - line_fitted_height_in_ems) / 2;

    $(":root").css("--base-maximum-block-height-em", `${MAXIMUM_BLOCK_HEIGHT_IN_EMS}em`);
    $(":root").css(
        "--line-fitted-vertical-align-offset-em",
        `${line_fitted_vertical_align_offset_in_ems}em`,
    );
}

export function set_base_typography_css_variables(): void {
    const font_size_px = user_settings.web_font_size_px;
    const line_height_percent = user_settings.web_line_height_percent;
    const line_height_unitless = line_height_percent / 100;
    const line_height_px = line_height_unitless * font_size_px;
    /* This percentage is a legacy value, rounding up from .294;
       additional logic might be useful to make this adjustable;
       likewise with the doubled value. */
    const markdown_interelement_space_fraction = 0.3;
    const markdown_interelement_space_px = line_height_px * markdown_interelement_space_fraction;

    $(":root").css("--base-line-height-unitless", line_height_unitless);
    $(":root").css("--base-font-size-px", `${font_size_px}px`);
    $(":root").css("--markdown-interelement-space-px", `${markdown_interelement_space_px}px`);
    $(":root").css(
        "--markdown-interelement-doubled-space-px",
        `${markdown_interelement_space_px * 2}px`,
    );

    set_vertical_alignment_values(line_height_unitless);
    resize.resize_page_components();
}

export function calculate_timestamp_widths(): void {
    const base_font_size_px = user_settings.web_font_size_px;
    const $temp_time_div = $("<div>");
    $temp_time_div.attr("id", "calculated-timestamp-widths");
    // Size the div to the width of the largest timestamp,
    // but the div out of the document flow with absolute
    // positioning.
    // We set the base font-size ordinarily on body so that
    // the correct em-size timestamps can be calculated along
    // with all the other information density values.
    $temp_time_div.css({
        "font-size": base_font_size_px,
        width: "max-content",
        visibility: "hidden",
        position: "absolute",
        top: "-100vh",
    });
    // We should get a reasonable max-width by looking only at
    // the first and last minutes of AM and PM
    const candidate_times = ["00:00", "11:59", "12:00", "23:59"];

    for (const time of candidate_times) {
        const $temp_time_element = $("<a>");
        $temp_time_element.attr("class", "message-time");
        // stringify_time only returns the time, so the date here is
        // arbitrary and only required for creating a Date object
        const candidate_timestamp = stringify_time(Date.parse(`1999-07-01T${time}`));
        $temp_time_element.text(candidate_timestamp);
        $temp_time_div.append($temp_time_element);
    }

    // Append the <div> element to calculate the maximum rendered width
    $("body").append($temp_time_div);
    const max_timestamp_width = $temp_time_div.width();
    // Set the width as a CSS variable
    $(":root").css("--message-box-timestamp-column-width", `${max_timestamp_width}px`);
    // Clean up by removing the temporary <div> element
    $temp_time_div.remove();
}

function determine_container_query_support(): void {
    const body = document.querySelector("body");
    const test_container = document.createElement("div");
    const test_child = document.createElement("div");
    test_container.classList.add("container-query-test");
    test_child.classList.add("container-query-test-child");
    test_container.append(test_child);

    body?.append(test_container);

    if (test_child?.getClientRects()[0]?.y === 0) {
        /* Conforming browsers will place the child element
           at the very top of the viewport. */
        body?.classList.add("with-container-query-support");
    } else {
        body?.classList.add("without-container-query-support");
    }

    test_container?.remove();
}

export function initialize(): void {
    set_base_typography_css_variables();
    // We calculate the widths of a candidate set of timestamps,
    // and use the largest to set `--message-box-timestamp-column-width`
    calculate_timestamp_widths();
    determine_container_query_support();
}

export const information_density_properties_schema = z.enum([
    "web_font_size_px",
    "web_line_height_percent",
]);

export function enable_or_disable_control_buttons($container: JQuery): void {
    const info_density_properties = z
        .array(information_density_properties_schema)
        .parse(["web_font_size_px", "web_line_height_percent"]);
    for (const property of info_density_properties) {
        const $button_group = $container.find(`[data-property='${CSS.escape(property)}']`);
        const $current_elem = $button_group.find<HTMLInputElement>(".current-value");
        const current_value = Number.parseInt($current_elem.val()!, 10);

        $button_group
            .find(".default-button")
            .prop("disabled", current_value === INFO_DENSITY_VALUES_DICT[property].default);
        $button_group
            .find(".increase-button")
            .prop("disabled", current_value >= INFO_DENSITY_VALUES_DICT[property].maximum);
        $button_group
            .find(".decrease-button")
            .prop("disabled", current_value <= INFO_DENSITY_VALUES_DICT[property].minimum);
    }
}

export function find_new_supported_value_for_setting(
    $elem: JQuery,
    property: "web_font_size_px" | "web_line_height_percent",
    current_value: number,
): number {
    if (current_value > INFO_DENSITY_VALUES_DICT[property].maximum) {
        return INFO_DENSITY_VALUES_DICT[property].maximum;
    }

    if (current_value < INFO_DENSITY_VALUES_DICT[property].minimum) {
        return INFO_DENSITY_VALUES_DICT[property].minimum;
    }

    // We know the value is inside the range of valid values, but not
    // a recommended value. This is only possible with line height,
    // where we allow any integer in the database, but only offer
    // certain steps in the UI.
    assert(property === "web_line_height_percent");

    if ($elem.hasClass("increase-button")) {
        return line_height_supported_values.find((valid_value) => valid_value > current_value)!;
    }

    return line_height_supported_values.findLast((valid_value) => valid_value < current_value)!;
}

export function check_setting_has_recommended_value(
    property: "web_font_size_px" | "web_line_height_percent",
    current_value: number,
): boolean {
    if (current_value > INFO_DENSITY_VALUES_DICT[property].maximum) {
        return false;
    }

    if (current_value < INFO_DENSITY_VALUES_DICT[property].minimum) {
        return false;
    }

    if (property === "web_font_size_px") {
        return true;
    }

    return line_height_supported_values.includes(current_value);
}

export function get_new_value_for_information_density_settings(
    $elem: JQuery,
    changed_property: "web_font_size_px" | "web_line_height_percent",
): number {
    const $current_elem = $elem.closest(".button-group").find<HTMLInputElement>(".current-value");
    const current_value = Number.parseInt($current_elem.val()!, 10);

    if ($elem.hasClass("default-button")) {
        return INFO_DENSITY_VALUES_DICT[changed_property].default;
    }

    if (!check_setting_has_recommended_value(changed_property, current_value)) {
        return find_new_supported_value_for_setting($elem, changed_property, current_value);
    }

    if ($elem.hasClass("increase-button")) {
        return current_value + INFO_DENSITY_VALUES_DICT[changed_property].step_value;
    }

    return current_value - INFO_DENSITY_VALUES_DICT[changed_property].step_value;
}

export function update_information_density_settings(
    $elem: JQuery,
    changed_property: "web_font_size_px" | "web_line_height_percent",
    for_settings_ui = false,
    new_value: number = get_new_value_for_information_density_settings($elem, changed_property),
): number {
    user_settings[changed_property] = new_value;
    $elem.closest(".button-group").find(".current-value").val(new_value);
    if (for_settings_ui) {
        let display_value = new_value.toString();
        if (changed_property === "web_line_height_percent") {
            display_value = get_string_display_value_for_line_height(new_value);
        }
        $elem.closest(".button-group").find(".display-value").text(display_value);
    }
    set_base_typography_css_variables();
    calculate_timestamp_widths();

    return new_value;
}

export function get_string_display_value_for_line_height(setting_value: number): string {
    const step_count =
        (setting_value - NON_COMPACT_MODE_LINE_HEIGHT_PERCENT) /
        INFO_DENSITY_VALUES_DICT.web_line_height_percent.step_value;
    let display_value;

    if (step_count % 1 === 0) {
        // If value is an integer, we just return here to avoid showing
        // 1.0 for 1.
        display_value = step_count.toString();
    } else {
        display_value = step_count.toFixed(1);
    }

    if (step_count > 0) {
        // We want to show "1" as "+1".
        return "+" + display_value;
    }
    return display_value;
}

export function get_tooltip_context_for_info_density_buttons(
    $elem: JQuery,
): Record<string, string | boolean> {
    const property = information_density_properties_schema.parse(
        $elem.closest(".button-group").attr("data-property"),
    );

    const is_default_button = $elem.hasClass("default-button");
    const new_value = get_new_value_for_information_density_settings($elem, property);
    const default_value = INFO_DENSITY_VALUES_DICT[property].default;
    const current_value = Number.parseInt(
        $elem.closest(".button-group").find<HTMLInputElement>(".current-value").val()!,
        10,
    );
    const is_current_value_default = current_value === default_value;

    let tooltip_first_line = "";
    let tooltip_second_line = "";
    if (property === "web_font_size_px") {
        if (is_default_button) {
            if (is_current_value_default) {
                tooltip_first_line = $t(
                    {defaultMessage: "Already at default font size ({default_value})"},
                    {default_value},
                );
            } else {
                tooltip_first_line = $t(
                    {defaultMessage: "Reset to default font size ({default_value})"},
                    {default_value},
                );
                tooltip_second_line = $t(
                    {defaultMessage: "Current font size: {current_value}"},
                    {current_value},
                );
            }
        } else if (!$elem.prop("disabled")) {
            tooltip_first_line = $t(
                {defaultMessage: "Change to font size {new_value}"},
                {new_value},
            );
        } else {
            if ($elem.hasClass("increase-button")) {
                const maximum_value = INFO_DENSITY_VALUES_DICT[property].maximum;
                if (current_value === maximum_value) {
                    tooltip_first_line = $t(
                        {defaultMessage: "Already at maximum font size ({maximum_value})"},
                        {maximum_value},
                    );
                } else {
                    tooltip_first_line = $t(
                        {
                            defaultMessage:
                                "Already above recommended maximum font size ({maximum_value})",
                        },
                        {maximum_value},
                    );
                }
            } else {
                const minimum_value = INFO_DENSITY_VALUES_DICT[property].minimum;
                if (current_value === minimum_value) {
                    tooltip_first_line = $t(
                        {defaultMessage: "Already at minimum font size ({minimum_value})"},
                        {minimum_value},
                    );
                } else {
                    tooltip_first_line = $t(
                        {
                            defaultMessage:
                                "Already below recommended minimum font size ({minimum_value})",
                        },
                        {minimum_value},
                    );
                }
            }
        }
    }

    if (property === "web_line_height_percent") {
        if (is_default_button) {
            if (is_current_value_default) {
                tooltip_first_line = $t({defaultMessage: "Already at default line spacing"});
            } else {
                const current_value_string =
                    get_string_display_value_for_line_height(current_value);
                tooltip_first_line = $t({defaultMessage: "Reset to default line spacing"});
                tooltip_second_line = $t(
                    {defaultMessage: "Current line spacing: {current_value_string}"},
                    {current_value_string},
                );
            }
        } else {
            if (!$elem.prop("disabled")) {
                if (new_value === default_value) {
                    tooltip_first_line = $t({defaultMessage: "Change to default line spacing"});
                } else {
                    const new_value_string = get_string_display_value_for_line_height(new_value);
                    tooltip_first_line = $t(
                        {defaultMessage: "Change to {new_value_string} line spacing"},
                        {new_value_string},
                    );
                }
            } else {
                if ($elem.hasClass("increase-button")) {
                    const maximum_value = INFO_DENSITY_VALUES_DICT[property].maximum;
                    if (current_value === maximum_value) {
                        tooltip_first_line = $t({
                            defaultMessage: "Already at maximum line spacing",
                        });
                    } else {
                        tooltip_first_line = $t({
                            defaultMessage: "Already above recommended maximum line spacing",
                        });
                    }
                } else {
                    const minimum_value = INFO_DENSITY_VALUES_DICT[property].minimum;
                    if (current_value === minimum_value) {
                        tooltip_first_line = $t({
                            defaultMessage: "Already at minimum line spacing",
                        });
                    } else {
                        tooltip_first_line = $t({
                            defaultMessage: "Already below recommended minimum line spacing",
                        });
                    }
                }
            }
        }
    }

    return {
        tooltip_first_line,
        tooltip_second_line,
    };
}

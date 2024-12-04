import $ from "jquery";

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

// Eventually these legacy values and references to them should be removed;
// but in the awkward stage where legacy values are in play for
// certain things (e.g., calculating line-height-based offsets for
// emoji alignment), it's necessary to have access to these values.
export const LEGACY_LINE_HEIGHT_UNITLESS = 1.214;
export const LEGACY_FONT_SIZE_PX = 14;
export const LEGACY_LINE_HEIGHT_PERCENT = 122;

export const NON_COMPACT_MODE_FONT_SIZE_PX = 16;
export const NON_COMPACT_MODE_LINE_HEIGHT_PERCENT = 140;

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
    const line_height_unitless = user_settings.dense_mode
        ? LEGACY_LINE_HEIGHT_UNITLESS
        : line_height_percent / 100;
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
}

export function calculate_timestamp_widths(): void {
    const base_font_size_px = user_settings.dense_mode
        ? LEGACY_FONT_SIZE_PX
        : user_settings.web_font_size_px;
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

export function initialize(): void {
    set_base_typography_css_variables();
    // We calculate the widths of a candidate set of timestamps,
    // and use the largest to set `--message-box-timestamp-column-width`
    calculate_timestamp_widths();
}

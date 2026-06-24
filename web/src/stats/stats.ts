import {
    type ActiveElement,
    ArcElement,
    BarController,
    BarElement,
    CategoryScale,
    Chart,
    type ChartDataset,
    type Chart as ChartInstance,
    type ChartOptions,
    Legend,
    LineController,
    LineElement,
    LinearScale,
    PieController,
    type Plugin,
    PointElement,
    TimeScale,
    Tooltip,
} from "chart.js";
import "chartjs-adapter-date-fns";
import zoomPlugin from "chartjs-plugin-zoom";
import {
    addDays,
    addMonths,
    addWeeks,
    addYears,
    differenceInCalendarDays,
    differenceInCalendarMonths,
    differenceInCalendarYears,
    startOfDay,
    startOfMonth,
    startOfWeek,
    startOfYear,
} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";
import * as z from "zod/mini";

import * as blueslip from "../blueslip.ts";
import {$t, $t_html} from "../i18n.ts";

import {page_params} from "./page_params.ts";

Chart.register(
    ArcElement,
    BarController,
    BarElement,
    CategoryScale,
    Legend,
    LineController,
    LineElement,
    LinearScale,
    PieController,
    PointElement,
    TimeScale,
    Tooltip,
    zoomPlugin,
);

Chart.defaults.font.family = "Open Sans, sans-serif";
Chart.defaults.color = "#000000";

// Define types
type DateFormatter = (date: Date) => string;

type AggregatedData<T> = {
    dates: Date[];
    values: T;
    last_value_is_partial: boolean;
};

type DataByEveryoneMe<T> = {
    everyone: T;
    me: T;
};

type DataByEveryoneUser<T> = {
    everyone: T;
    user: T;
};

type DataByUserType<T> = {
    human: T;
    bot: T;
    me: T;
};

type DataByTime<T> = {
    cumulative: T;
    year: T;
    month: T;
    week: T;
};

// A single view (daily/weekly/cumulative) of a time-series chart, ready to
// hand to Chart.js. Bars and the cumulative line share one chart instance, so
// each series carries its own per-point background colors (used to dim the
// trailing partial bar).
type ChartSeries = {
    data: number[];
    // Solid series color, used when drawn as the cumulative line.
    color: string;
    // Per-point colors, used when drawn as bars; dims the trailing partial bar.
    bar_colors: string[];
};

type ChartView = {
    // x-axis values, plotted on a continuous time scale.
    times: Date[];
    // Formatted date for each point, shown in the custom hover readout.
    hover_text: string[];
    type: "bar" | "line";
    series: ChartSeries[];
    // Finest tick interval, in days, for this view (7 for the weekly views so
    // their labels never fall finer than a week).
    min_step_days: number;
};

// Server analytics counts are always non-negative integers.
const datum_schema = z.number();

// Define a schema factory function for the utility generic type
function instantiate_type_DataByEveryoneUser<T extends z.ZodMiniType>(
    schema: T,
): z.ZodMiniObject<{everyone: T; user: T}> {
    return z.object({
        everyone: schema,
        user: schema,
    });
}

// Define zod schemas for incoming data from the server
const common_data_schema = z.object({
    end_times: z.array(z.number()),
});

const active_user_data = z.object({
    _1day: z.array(datum_schema),
    _15day: z.array(datum_schema),
    all_time: z.array(datum_schema),
});

const read_data_schema = z.object({
    ...instantiate_type_DataByEveryoneUser(z.object({read: z.array(z.number())})).shape,
    ...common_data_schema.shape,
});

const sent_data_schema = z.object({
    ...instantiate_type_DataByEveryoneUser(
        z.object({
            human: z.array(z.number()),
            bot: z.array(z.number()),
        }),
    ).shape,
    ...common_data_schema.shape,
});

const ordered_sent_data_schema = z.object({
    ...instantiate_type_DataByEveryoneUser(z.record(z.string(), z.array(z.number()))).shape,
    ...common_data_schema.shape,
    display_order: z.array(z.string()),
});

const user_count_data_schema = z.object({
    ...z.object({everyone: active_user_data}).shape,
    ...common_data_schema.shape,
});

// Inferred types used in nested functions
type SentData = z.infer<typeof sent_data_schema>;
type OrderedSentData = z.infer<typeof ordered_sent_data_schema>;
type ReadData = z.infer<typeof read_data_schema>;
type ActiveUserData = z.infer<typeof active_user_data>;

// Define misc zod schemas
const time_button_schema = z.enum(["cumulative", "year", "month", "week"]);
const user_button_schema = z.enum(["everyone", "user"]);

// Series colors, matched to the previous Plotly implementation.
const color_humans = "#5f6ea0";
const color_bots = "#b7b867";
const color_me = "#be6d68";
const color_everyone = "#5f6ea0";
const color_by_client = "#537c5e";
// The first three colors match the previous Plotly implementation; any further
// slices fall back to Plotly's former default colorway (starting with blue),
// so recipient types beyond the first three keep the colors they had before.
const pie_colors = [
    "#68537c",
    "#be6d68",
    "#b3b348",
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
];

const legend_font_size = 14;
const tick_font_size = 12;

const DAY_MS = 24 * 60 * 60 * 1000;

// Smallest range the x-axis can be zoomed to. Kept at or above the coarsest
// data spacing (weekly) so at least a couple of data points stay visible in
// every view — zooming in further would otherwise land between points and show
// nothing. Being uniform across views also means switching views never lands on
// a range that's invalid for the new view.
const min_x_range_ms = 14 * DAY_MS;

// Zoom factor applied per pixel of accumulated wheel scrolling, as an exponent
// (see attach_time_series_interactions). Tuned so a typical mouse-wheel notch
// (~100px) zooms about 10%, which stays gentle and controllable when a
// high-resolution touchpad reports many small deltas.
const wheel_zoom_rate = 0.001;

// Replaces Plotly's range slider: the mouse wheel zooms the x-axis, dragging
// pans it, and double-clicking resets to the full range. Drag is reserved for
// panning, so box-select zooming (zoom.drag) is intentionally left disabled —
// enabling both makes a single drag pan and draw a zoom rectangle at once. The
// wheel handler is also disabled here and reimplemented in
// attach_time_series_interactions so we can throttle redraws to one per frame.
const x_zoom_options = {
    zoom: {
        wheel: {enabled: false},
        mode: "x" as const,
    },
    pan: {enabled: true, mode: "x" as const},
    // Clamp panning/zooming to the original data range (so zooming out can't run
    // away into an empty, ever-growing range) and to a minimum window (so
    // zooming in can't land between data points and show nothing).
    limits: {
        x: {min: "original" as const, max: "original" as const, minRange: min_x_range_ms},
    },
};

let last_full_update = Number.POSITIVE_INFINITY;

function handle_parse_server_stats_result<T>(
    result: z.core.util.SafeParseResult<T>,
): T | undefined {
    if (!result.success) {
        blueslip.warn(
            "Server stats data cannot be parsed as expected.\n" +
                "Check if the schema is up-to-date or the data satisfies the schema definition.",
            {
                issues: result.error.issues,
            },
        );
        return undefined;
    }
    return result.data;
}

// Copied from attachments_ui.js
function bytes_to_size(bytes: number, kb_with_1024_bytes = false): string {
    const kb_size = kb_with_1024_bytes ? 1024 : 1000;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    if (bytes === 0) {
        return "0 B";
    }
    const i = Math.round(Math.floor(Math.log(bytes) / Math.log(kb_size)));
    let size = Math.round(bytes / Math.pow(kb_size, i));
    if (i > 0 && size < 10) {
        size = Math.round((bytes / Math.pow(kb_size, i)) * 10) / 10;
    }
    return `${size} ${sizes[i]}`;
}

// TODO: should take a dict of arrays and do it for all keys
function partial_sums(array: number[]): number[] {
    let accumulator = 0;
    return array.map((o) => {
        accumulator += o;
        return accumulator;
    });
}

// Assumes date is a round number of hours
function floor_to_local_day(date: Date): Date {
    const date_copy = new Date(date);
    date_copy.setHours(0);
    return date_copy;
}

// Assumes date is a round number of hours
function floor_to_local_week(date: Date): Date {
    const date_copy = floor_to_local_day(date);
    date_copy.setHours(-24 * date.getDay());
    return date_copy;
}

function format_date(date: Date, include_hour: boolean): string {
    const months = [
        $t({defaultMessage: "January"}),
        $t({defaultMessage: "February"}),
        $t({defaultMessage: "March"}),
        $t({defaultMessage: "April"}),
        $t({defaultMessage: "May"}),
        $t({defaultMessage: "June"}),
        $t({defaultMessage: "July"}),
        $t({defaultMessage: "August"}),
        $t({defaultMessage: "September"}),
        $t({defaultMessage: "October"}),
        $t({defaultMessage: "November"}),
        $t({defaultMessage: "December"}),
    ];
    const month_str = months[date.getMonth()];
    const year = date.getFullYear();
    const day = date.getDate();
    if (include_hour) {
        const hour = date.getHours();

        const str = hour >= 12 ? "PM" : "AM";

        return `${month_str} ${day}, ${hour % 12}:00${str}`;
    }
    return `${month_str} ${day}, ${year}`;
}

function update_last_full_update(end_times: number[]): void {
    if (end_times.length === 0) {
        return;
    }

    last_full_update = Math.min(last_full_update, end_times.at(-1)!);
    const update_time = new Date(last_full_update * 1000);
    const locale_date = update_time.toLocaleDateString("en-US", {
        year: "numeric",
        month: "long",
        day: "numeric",
    });
    const locale_time = update_time.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "numeric",
    });

    $("#id_last_full_update").text(locale_time + " on " + locale_date);
    $("#id_last_full_update").closest(".last-update").show();
}

$(() => {
    tippy.default(".last_update_tooltip", {
        // Same defaults as set in our tippyjs module.
        maxWidth: 300,
        delay: [100, 20],
        animation: false,
        touch: ["hold", 750],
        placement: "top",
    });
    // Add configuration for any additional tooltips here.
});

// Replace a chart container's loading spinner with a fresh <canvas> for
// Chart.js to render into, and return that canvas's drawing context.
function create_chart_canvas(container_id: string): CanvasRenderingContext2D {
    const container = document.querySelector<HTMLElement>(`#${container_id}`)!;
    container.querySelector(".spinner")?.remove();
    const canvas = document.createElement("canvas");
    container.append(canvas);
    return canvas.getContext("2d")!;
}

// Build the per-point background colors for a bar series, dimming the final
// bar when it represents a partial (still-accumulating) day or week.
function bar_backgrounds(color: string, count: number, last_value_is_partial: boolean): string[] {
    const colors = Array.from({length: count}, () => color);
    if (last_value_is_partial && count > 0) {
        // Append a 50%-opacity alpha channel to the hex color.
        colors[count - 1] = color + "80";
    }
    return colors;
}

// Deterministic x-axis tick generation. Chart.js's automatic time ticks anchor
// to the start of the visible range and pick "nice" day step-sizes (1, 2, 3,
// 5, ...), so panning reshuffles which dates are labeled, weekly bars get 6/8-
// day labels, and the edge padding it derives from the tick spacing jolts the
// view when the step changes at a zoom threshold. Instead we lay ticks on a
// fixed calendar grid (anchored to a constant epoch, never to the visible
// range) at a week-aware interval chosen from the zoom level.
type TickStep = {
    approx_days: number;
    // Largest grid boundary at or before `time`.
    floor: (time: number) => Date;
    // Advance by one interval.
    next: (date: Date) => Date;
};

function calendar_step(
    approx_days: number,
    start_of: (date: Date) => Date,
    add: (date: Date, amount: number) => Date,
    units_between: (later: Date, earlier: Date) => number,
    multiple: number,
): TickStep {
    // A fixed reference; its value only sets the phase of multi-unit steps.
    const epoch = start_of(new Date(2001, 0, 1));
    return {
        approx_days,
        floor(time) {
            const boundary = start_of(new Date(time));
            const units = units_between(boundary, epoch);
            return add(epoch, Math.floor(units / multiple) * multiple);
        },
        next: (date) => add(date, multiple),
    };
}

const weeks_between = (later: Date, earlier: Date): number =>
    Math.round(differenceInCalendarDays(later, earlier) / 7);

// Candidate intervals, ascending. Week-based steps keep weekly bars' labels
// aligned to weeks; day/month/year steps cover finer and coarser zoom levels.
const TICK_STEPS: TickStep[] = [
    calendar_step(1, startOfDay, addDays, differenceInCalendarDays, 1),
    calendar_step(2, startOfDay, addDays, differenceInCalendarDays, 2),
    calendar_step(7, startOfWeek, addWeeks, weeks_between, 1),
    calendar_step(14, startOfWeek, addWeeks, weeks_between, 2),
    calendar_step(30, startOfMonth, addMonths, differenceInCalendarMonths, 1),
    calendar_step(61, startOfMonth, addMonths, differenceInCalendarMonths, 2),
    calendar_step(91, startOfMonth, addMonths, differenceInCalendarMonths, 3),
    calendar_step(182, startOfMonth, addMonths, differenceInCalendarMonths, 6),
    calendar_step(365, startOfYear, addYears, differenceInCalendarYears, 1),
];

const TARGET_TICK_COUNT = 11;

// `min_step_days` is the finest allowed interval; the weekly view passes 7 so
// its labels are never finer than a week.
function time_axis_ticks(min: number, max: number, min_step_days: number): {value: number}[] {
    const span_days = (max - min) / DAY_MS;
    const candidates = TICK_STEPS.filter((step) => step.approx_days >= min_step_days);
    const step =
        candidates.find((candidate) => span_days / candidate.approx_days <= TARGET_TICK_COUNT) ??
        candidates.at(-1)!;
    const ticks: {value: number}[] = [];
    let date = step.floor(min);
    while (date.getTime() < min) {
        date = step.next(date);
    }
    while (date.getTime() <= max) {
        ticks.push({value: date.getTime()});
        date = step.next(date);
    }
    return ticks;
}

const day_tick_format = new Intl.DateTimeFormat(undefined, {month: "short", day: "numeric"});
const month_tick_format = new Intl.DateTimeFormat(undefined, {month: "short", year: "numeric"});
const year_tick_format = new Intl.DateTimeFormat(undefined, {year: "numeric"});

// Choose the label granularity from the tick spacing, so labels match the
// interval without an auto unit switch jolting the zoom.
function format_time_tick(
    value: number | string,
    _index: number,
    ticks: {value: number | string}[],
): string {
    const spacing_days =
        ticks.length > 1 ? (Number(ticks[1]!.value) - Number(ticks[0]!.value)) / DAY_MS : 0;
    const date = new Date(Number(value));
    if (spacing_days >= 320) {
        return year_tick_format.format(date);
    }
    if (spacing_days >= 27) {
        return month_tick_format.format(date);
    }
    return day_tick_format.format(date);
}

// Horizontal room to reserve for the edge tick labels, sized to half the widest
// possible label (a month-and-year, measured across all months for the active
// locale). Chart.js otherwise derives this padding from the first/last visible
// label, so panning a label toward the edge would shrink the plot — a slight
// zoom — until the label drops off and the plot snapped back to full width.
// Pinning it to this constant (see time_series_options' afterFit) keeps the
// plot width fixed while panning, and ensures edge labels never clip.
function max_tick_label_half_width(): number {
    const context = document.createElement("canvas").getContext("2d")!;
    context.font = `${tick_font_size}px "Open Sans", sans-serif`;
    let widest = 0;
    for (let month = 0; month < 12; month += 1) {
        const label = month_tick_format.format(new Date(2026, month, 1));
        widest = Math.max(widest, context.measureText(label).width);
    }
    return widest / 2;
}

const x_edge_padding = Math.ceil(max_tick_label_half_width());

// Shared options for the date-indexed bar/line charts (messages sent/read over
// time, active users). The x-axis pans and zooms in place of Plotly's range
// slider, and the built-in tooltip is disabled in favor of our custom hover
// readout.
function time_series_options(
    show_legend: boolean,
    min_tick_step_days: () => number,
): ChartOptions<"bar" | "line"> {
    return {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {mode: "index", intersect: false},
        scales: {
            // A continuous time axis (rather than a discrete category axis) so
            // that wheel zoom and drag pan are smooth and behave consistently
            // regardless of how many data points a view has. offset: false
            // keeps edge padding from depending on tick spacing, so the view
            // doesn't jump when the tick interval changes at a zoom threshold.
            x: {
                type: "time",
                offset: false,
                grid: {display: false},
                afterBuildTicks(axis) {
                    axis.ticks = time_axis_ticks(axis.min, axis.max, min_tick_step_days());
                },
                // Keep the edge-label padding constant so panning a label past
                // the plot edge doesn't resize (and visibly zoom) the plot.
                afterFit(axis) {
                    axis.paddingLeft = x_edge_padding;
                    axis.paddingRight = x_edge_padding;
                },
                ticks: {
                    autoSkip: false,
                    maxRotation: 0,
                    font: {size: tick_font_size},
                    callback: format_time_tick,
                },
            },
            y: {beginAtZero: true, ticks: {font: {size: tick_font_size}}},
        },
        plugins: {
            legend: {
                display: show_legend,
                position: "top",
                labels: {font: {size: legend_font_size}},
            },
            tooltip: {enabled: false},
            zoom: x_zoom_options,
        },
    };
}

// Construct fresh Chart.js datasets for a time-series view. We rebuild rather
// than mutate so that switching between the bar (daily/weekly) and line
// (cumulative) views is a clean type swap; `hidden` carries the user's current
// legend selections across the swap.
function build_time_series_datasets(
    view: ChartView,
    names: string[],
    hidden: boolean[],
): ChartDataset<"bar" | "line", number[]>[] {
    return view.series.map((series, i) => {
        if (view.type === "line") {
            return {
                type: "line",
                label: names[i],
                data: series.data,
                borderColor: series.color,
                backgroundColor: series.color,
                pointRadius: 0,
                hidden: hidden[i],
            } satisfies ChartDataset<"line", number[]>;
        }
        return {
            type: "bar",
            label: names[i],
            data: series.data,
            backgroundColor: series.bar_colors,
            hidden: hidden[i],
        } satisfies ChartDataset<"bar", number[]>;
    });
}

// SUMMARY STATISTICS
function get_user_summary_statistics(data: ActiveUserData): void {
    if (Object.keys(data).length === 0) {
        return;
    }

    // Users that are not deactivated and are not bots.
    const total_users = data.all_time.at(-1)!;
    const total_users_string = total_users.toLocaleString();

    $("#id_total_users").text(total_users_string);
    $("#id_total_users").closest("summary-stats").show();

    // Users that have been active in the last 15 days and are not bots.
    const active_fifeteen_day_users = data._15day.at(-1)!;
    const active_fifteen_day_users_string = active_fifeteen_day_users.toLocaleString();

    $("#id_active_fifteen_day_users").text(active_fifteen_day_users_string);
    $("#id_active_fifteen_day_users").closest("summary-stats").show();
}

function get_total_messages_sent(data: DataByUserType<number[]>): void {
    if (Object.keys(data).length === 0) {
        return;
    }

    const total_messages_sent = data.human.at(-1)! + data.bot.at(-1)!;
    const total_messages_string = total_messages_sent.toLocaleString();

    $("#id_total_messages_sent").text(total_messages_string);
    $("#id_total_messages_sent").closest("summary-stats").show();
}

function get_thirty_days_messages_sent(data: DataByUserType<number[]>): void {
    if (Object.keys(data).length === 0) {
        return;
    }

    const thirty_days_bot_messages = data.bot
        .slice(-30)
        .reduce((total_messages, day_messages) => total_messages + day_messages);
    const thirty_days_human_messages = data.human
        .slice(-30)
        .reduce((total_messages, day_messages) => total_messages + day_messages);

    const thirty_days_total_messages = thirty_days_bot_messages + thirty_days_human_messages;
    const thirty_days_messages_string = thirty_days_total_messages.toLocaleString();

    $("#id_thirty_days_messages_sent").text(thirty_days_messages_string);
    $("#id_thirty_days_messages_sent").closest("summary-stats").show();
}

function set_storage_space_used_statistic(upload_space_used: number | null): void {
    let space_used = "N/A";
    if (upload_space_used !== null) {
        space_used = bytes_to_size(upload_space_used, true);
    }

    $("#id_storage_space_used").text(space_used);
    $("#id_storage_space_used").closest("summary-stats").show();
}

function set_guest_users_statistic(guest_users: number | null): void {
    let guest_users_string = "N/A";
    if (guest_users !== null) {
        guest_users_string = guest_users.toLocaleString();
    }

    $("#id_guest_users_count").text(guest_users_string);
    $("#id_guest_users_count").closest("summary-stats").show();
}

// CHARTS

// Wire up the pointer interactions for a date-indexed bar/line chart: the
// custom hover readout, double-click-to-reset, and smooth wheel zoom. Chart.js's
// built-in tooltip is disabled in favor of the dedicated hover DOM elements, as
// the previous Plotly implementation did. `text` holds the formatted date for
// each x-index; `rows` maps each hover row to its series (dataset index) and the
// DOM elements that label and display its value.
function attach_time_series_interactions(
    chart: ChartInstance,
    info_id: string,
    date_id: string,
    text: () => string[],
    rows: {dataset_index: number; label_id: string | undefined; value_id: string}[],
): void {
    const $info = $(`#${info_id}`);

    function hide(): void {
        $info.hide();
    }

    function show(index: number): void {
        $info.show();
        document.querySelector(`#${date_id}`)!.textContent = text()[index] ?? "";
        for (const row of rows) {
            const value = chart.data.datasets[row.dataset_index]?.data[index];
            const $value = $(`#${row.value_id}`);
            const $label = row.label_id === undefined ? undefined : $(`#${row.label_id}`);
            if (typeof value === "number") {
                $label?.css("display", "inline");
                $value.css("display", "inline").text(value.toString());
            } else {
                $label?.css("display", "none");
                $value.css("display", "none");
            }
        }
    }

    chart.options.onHover = (_event, elements: ActiveElement[]) => {
        if (elements.length === 0) {
            hide();
        } else {
            show(elements[0]!.index);
        }
    };

    const {canvas} = chart;

    // onHover doesn't fire once the pointer leaves the canvas, so clear the
    // readout explicitly on mouseleave.
    canvas.addEventListener("mouseleave", hide);

    // Double-click resets any pan/zoom back to the full range.
    canvas.addEventListener("dblclick", () => {
        chart.resetZoom();
    });

    // Smooth wheel zoom. The plugin's own wheel handler is disabled (see
    // x_zoom_options) because it zooms a fixed amount per wheel event and
    // redraws synchronously for each one — too fast, and very slow to render,
    // with high-resolution touchpads that emit many events per gesture. Instead
    // we accumulate the scroll distance and apply a single, distance-
    // proportional zoom once per animation frame, redrawing only the final
    // state for that frame.
    let pending_delta = 0;
    let focal_point = {x: 0, y: 0};
    let frame_request: number | undefined;

    function apply_wheel_zoom(): void {
        frame_request = undefined;
        // Scrolling up (negative deltaY) zooms in; scrolling down zooms out.
        const factor = Math.exp(-pending_delta * wheel_zoom_rate);
        pending_delta = 0;
        chart.zoom({x: factor, focalPoint: focal_point}, "none");
    }

    canvas.addEventListener(
        "wheel",
        (event) => {
            event.preventDefault();
            // Normalize line- and page-based delta modes to approximate pixels.
            const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 400 : 1;
            pending_delta += event.deltaY * unit;
            const rect = canvas.getBoundingClientRect();
            focal_point = {x: event.clientX - rect.left, y: event.clientY - rect.top};
            frame_request ??= requestAnimationFrame(apply_wheel_zoom);
        },
        {passive: false},
    );
}

function populate_messages_sent_over_time(raw_data: unknown): void {
    // Content rendered by this method is titled as "Messages sent over time" on the webpage
    const result = sent_data_schema.safeParse(raw_data);
    const data = handle_parse_server_stats_result(result);
    if (data === undefined) {
        return;
    }

    if (data.end_times.length === 0) {
        // TODO: do something nicer here
        return;
    }

    const start_dates = data.end_times.map(
        (timestamp: number) =>
            // data.end_times are the ends of hour long intervals.
            new Date(timestamp * 1000 - 60 * 60 * 1000),
    );

    function aggregate_data(
        data: SentData,
        aggregation: "day" | "week",
    ): AggregatedData<DataByUserType<number[]>> {
        let start;
        let is_boundary;
        if (aggregation === "day") {
            start = floor_to_local_day(start_dates[0]!);
            is_boundary = function (date: Date) {
                return date.getHours() === 0;
            };
        } else {
            assert(aggregation === "week");
            start = floor_to_local_week(start_dates[0]!);
            is_boundary = function (date: Date) {
                return date.getHours() === 0 && date.getDay() === 0;
            };
        }
        const dates = [start];
        const values: DataByUserType<number[]> = {human: [], bot: [], me: []};
        let current: DataByUserType<number> = {human: 0, bot: 0, me: 0};
        let i_init = 0;
        if (is_boundary(start_dates[0]!)) {
            current = {
                human: data.everyone.human[0]!,
                bot: data.everyone.bot[0]!,
                me: data.user.human[0]!,
            };
            i_init = 1;
        }
        for (let i = i_init; i < start_dates.length; i += 1) {
            if (is_boundary(start_dates[i]!)) {
                dates.push(start_dates[i]!);
                values.human.push(current.human);
                values.bot.push(current.bot);
                values.me.push(current.me);
                current = {human: 0, bot: 0, me: 0};
            }
            current.human += data.everyone.human[i]!;
            current.bot += data.everyone.bot[i]!;
            current.me += data.user.human[i]!;
        }
        values.human.push(current.human);
        values.bot.push(current.bot);
        values.me.push(current.me);
        return {
            dates,
            values,
            last_value_is_partial: !is_boundary(
                new Date(start_dates.at(-1)!.getTime() + 60 * 60 * 1000),
            ),
        };
    }

    // Build the three views. The series order is [me, humans, bots] to match
    // the dataset order created below.
    function make_view(
        dates: Date[],
        values: DataByUserType<number[]>,
        type: "bar" | "line",
        last_value_is_partial: boolean,
        min_step_days: number,
        date_formatter: DateFormatter,
    ): ChartView {
        return {
            times: dates,
            hover_text: dates.map((date) => date_formatter(date)),
            type,
            min_step_days,
            series: [
                {
                    data: values.me,
                    color: color_me,
                    bar_colors: bar_backgrounds(color_me, values.me.length, last_value_is_partial),
                },
                {
                    data: values.human,
                    color: color_humans,
                    bar_colors: bar_backgrounds(
                        color_humans,
                        values.human.length,
                        last_value_is_partial,
                    ),
                },
                {
                    data: values.bot,
                    color: color_bots,
                    bar_colors: bar_backgrounds(
                        color_bots,
                        values.bot.length,
                        last_value_is_partial,
                    ),
                },
            ],
        };
    }

    const daily_info = aggregate_data(data, "day");
    const daily_view = make_view(daily_info.dates, daily_info.values, "bar", true, 1, (date) =>
        format_date(date, false),
    );
    get_thirty_days_messages_sent(daily_info.values);

    const weekly_info = aggregate_data(data, "week");
    const weekly_view = make_view(weekly_info.dates, weekly_info.values, "bar", true, 7, (date) =>
        $t({defaultMessage: "Week of {date}"}, {date: format_date(date, false)}),
    );

    const cumulative_dates = data.end_times.map((timestamp: number) => new Date(timestamp * 1000));
    const cumulative_values = {
        me: partial_sums(data.user.human),
        human: partial_sums(data.everyone.human),
        bot: partial_sums(data.everyone.bot),
    };
    const cumulative_view = make_view(
        cumulative_dates,
        cumulative_values,
        "line",
        false,
        1,
        (date) => format_date(date, true),
    );
    get_total_messages_sent(cumulative_values);

    const ctx = create_chart_canvas("id_messages_sent_over_time");
    const series_names = [
        $t({defaultMessage: "Me"}),
        $t({defaultMessage: "Humans"}),
        $t({defaultMessage: "Bots"}),
    ];
    // Default visibility: only "Humans" is shown; "Me" and "Bots" start hidden
    // but can be toggled on from the legend.
    const default_hidden = [true, false, true];

    let current_hover_text: string[] = [];
    let current_min_step_days = 1;
    let chart: ChartInstance<"bar" | "line", number[], Date> | undefined;

    function draw_plot(view: ChartView): void {
        current_hover_text = view.hover_text;
        current_min_step_days = view.min_step_days;
        const hidden =
            chart === undefined
                ? default_hidden
                : series_names.map((_, i) => !chart!.isDatasetVisible(i));
        const datasets = build_time_series_datasets(view, series_names, hidden);
        if (chart === undefined) {
            chart = new Chart<"bar" | "line", number[], Date>(ctx, {
                type: "bar",
                data: {labels: view.times, datasets},
                options: time_series_options(true, () => current_min_step_days),
            });
            attach_time_series_interactions(
                chart,
                "hoverinfo",
                "hover_date",
                () => current_hover_text,
                [
                    {dataset_index: 0, label_id: "hover_me", value_id: "hover_me_value"},
                    {dataset_index: 1, label_id: "hover_human", value_id: "hover_human_value"},
                    {dataset_index: 2, label_id: "hover_bot", value_id: "hover_bot_value"},
                ],
            );
        } else {
            // Keep the current zoom/pan range when switching daily/weekly/
            // cumulative views.
            chart.data.labels = view.times;
            chart.data.datasets = datasets;
            chart.update();
        }
    }

    $("#daily_button").on("click", function () {
        draw_plot(daily_view);
        $("#daily_button, #weekly_button, #cumulative_button").removeClass("selected");
        $(this).addClass("selected");
    });

    $("#weekly_button").on("click", function () {
        draw_plot(weekly_view);
        $("#daily_button, #weekly_button, #cumulative_button").removeClass("selected");
        $(this).addClass("selected");
    });

    $("#cumulative_button").on("click", function () {
        draw_plot(cumulative_view);
        $("#daily_button, #weekly_button, #cumulative_button").removeClass("selected");
        $(this).addClass("selected");
    });

    // Initial drawing of plot
    if (weekly_view.times.length < 12) {
        draw_plot(daily_view);
        $("#daily_button").addClass("selected");
    } else {
        draw_plot(weekly_view);
        $("#weekly_button").addClass("selected");
    }
}

function round_to_percentages(values: number[], total: number): string[] {
    return values.map((x) => {
        if (x === total) {
            return "100%";
        }
        if (x === 0) {
            return "0%";
        }
        const unrounded = (x / total) * 100;

        const precision = Math.min(
            6, // this is the max precision (two #, 4 decimal points; 99.9999%).
            Math.max(
                2, // the minimum amount of precision (40% or 6.0%).
                Math.floor(-Math.log10(100 - unrounded)) + 3,
            ),
        );

        return unrounded.toPrecision(precision) + "%";
    });
}

// Last label will turn into "Other" if time_series data has a label not in labels
function compute_summary_chart_data(
    time_series_data: Record<string, number[]>,
    num_steps: number,
    labels_: string[],
): {
    values: number[];
    labels: string[];
    percentages: string[];
    total: number;
} {
    const data = new Map<string, number>();
    for (const [key, array] of Object.entries(time_series_data)) {
        if (array.length < num_steps) {
            num_steps = array.length;
        }
        let sum = 0;
        for (let i = 1; i <= num_steps; i += 1) {
            sum += array.at(-i)!;
        }
        data.set(key, sum);
    }
    const labels = [...labels_];
    const values: number[] = [];
    for (const label of labels) {
        if (data.has(label)) {
            values.push(data.get(label)!);
            data.delete(label);
        } else {
            values.push(0);
        }
    }
    if (data.size > 0) {
        labels[labels.length - 1] = "Other";
        for (const sum of data.values()) {
            values[labels.length - 1]! += sum;
        }
    }
    let total = 0;
    for (const value of values) {
        total += value;
    }
    return {
        values,
        labels,
        percentages: round_to_percentages(values, total),
        total,
    };
}

function populate_messages_sent_by_client(raw_data: unknown): void {
    // Content rendered by this method is titled as "Messages sent by client" on the webpage
    const result = ordered_sent_data_schema.safeParse(raw_data);
    const data = handle_parse_server_stats_result(result);
    if (data === undefined) {
        return;
    }

    // A horizontal bar chart with the client name and percentage drawn at the
    // end of each bar.
    type ClientPlotData = {
        labels: string[];
        values: number[];
        annotations: string[];
    };

    // sort labels so that values are descending in the default view
    const everyone_month = compute_summary_chart_data(
        data.everyone,
        30,
        data.display_order.slice(0, 12),
    );
    const label_values: {label: string; value: number}[] = [];
    for (let i = 0; i < everyone_month.values.length; i += 1) {
        label_values.push({
            label: everyone_month.labels[i]!,
            value: everyone_month.labels[i] === "Other" ? -1 : everyone_month.values[i]!,
        });
    }
    label_values.sort((a, b) => b.value - a.value);
    const labels: string[] = [];
    for (const item of label_values) {
        labels.push(item.label);
    }

    function make_plot_data(
        time_series_data: Record<string, number[]>,
        num_steps: number,
    ): ClientPlotData {
        const plot_data = compute_summary_chart_data(time_series_data, num_steps, labels);
        const annotations = plot_data.values.map((value, i) =>
            value > 0 ? `${plot_data.labels[i]} (${plot_data.percentages[i]})` : "",
        );
        return {
            labels: plot_data.labels,
            values: plot_data.values,
            annotations,
        };
    }

    const plot_data: DataByEveryoneUser<DataByTime<ClientPlotData>> = {
        everyone: {
            cumulative: make_plot_data(data.everyone, data.end_times.length),
            year: make_plot_data(data.everyone, 365),
            month: make_plot_data(data.everyone, 30),
            week: make_plot_data(data.everyone, 7),
        },
        user: {
            cumulative: make_plot_data(data.user, data.end_times.length),
            year: make_plot_data(data.user, 365),
            month: make_plot_data(data.user, 30),
            week: make_plot_data(data.user, 7),
        },
    };

    let user_button: "everyone" | "user" = "everyone";
    let time_button: "cumulative" | "year" | "month" | "week";
    if (data.end_times.length >= 30) {
        time_button = "month";
        $("#messages_by_client_last_month_button").addClass("selected");
    } else {
        time_button = "cumulative";
        $("#messages_by_client_cumulative_button").addClass("selected");
    }

    if (data.end_times.length < 365) {
        $("#messages_sent_by_client button[data-time='year']").remove();
        if (data.end_times.length < 30) {
            $("#messages_sent_by_client button[data-time='month']").remove();
            if (data.end_times.length < 7) {
                $("#messages_sent_by_client button[data-time='week']").remove();
            }
        }
    }

    // The "Client (xx%)" label drawn just past the end of each bar, indexed to
    // match the current dataset; updated by draw_plot.
    let annotations: string[] = [];

    // Draws the per-bar annotation text onto the canvas.
    const annotation_plugin: Plugin<"bar"> = {
        id: "client_annotations",
        afterDatasetsDraw(chart) {
            const {ctx} = chart;
            const meta = chart.getDatasetMeta(0);
            ctx.save();
            ctx.font = `${legend_font_size}px Open Sans, sans-serif`;
            ctx.fillStyle = "#000000";
            ctx.textBaseline = "middle";
            for (const [i, element] of meta.data.entries()) {
                if (annotations[i]) {
                    ctx.fillText(annotations[i], element.x + 6, element.y);
                }
            }
            ctx.restore();
        },
    };

    const ctx = create_chart_canvas("messages_sent_by_client_chart");
    const dataset: ChartDataset<"bar", number[]> = {
        data: [],
        backgroundColor: color_by_client,
    };
    const chart = new Chart<"bar", number[], string>(ctx, {
        type: "bar",
        data: {labels: [], datasets: [dataset]},
        plugins: [annotation_plugin],
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            // Static plot: no hover/tooltip interactions.
            events: [],
            scales: {
                x: {beginAtZero: true, ticks: {font: {size: legend_font_size}}},
                y: {ticks: {display: false}, grid: {display: false}},
            },
            plugins: {
                legend: {display: false},
            },
        },
    });

    function draw_plot(): void {
        const data_ = plot_data[user_button][time_button];
        // Leave room to the right of the longest bar for its text label.
        const container = document.querySelector<HTMLElement>("#messages_sent_by_client_chart")!;
        container.style.height = `${40 + data_.labels.length * 30}px`;
        chart.resize();
        chart.data.labels = data_.labels;
        dataset.data = data_.values;
        chart.options.scales!["x"]!.max = Math.max(...data_.values, 0) * 1.3;
        annotations = data_.annotations;
        chart.update();
    }

    draw_plot();

    // Click handlers
    function set_user_button($button: JQuery): void {
        $("#messages_sent_by_client button[data-user]").removeClass("selected");
        $button.addClass("selected");
    }

    function set_time_button($button: JQuery): void {
        $("#messages_sent_by_client button[data-time]").removeClass("selected");
        $button.addClass("selected");
    }

    $("#messages_sent_by_client button").on("click", function () {
        if ($(this).attr("data-user")) {
            set_user_button($(this));
            user_button = user_button_schema.parse($(this).attr("data-user"));
            // Now `user_button` will be of type "everyone" | "user"
        }
        if ($(this).attr("data-time")) {
            set_time_button($(this));
            time_button = time_button_schema.parse($(this).attr("data-time"));
            // Now `time_button` will be of type "cumulative" | "year" | "month" | "week"
        }
        draw_plot();
    });
}

function populate_messages_sent_by_message_type(raw_data: unknown): void {
    // Content rendered by this method is titled as "Messages sent by recipient type" on the webpage
    const result = ordered_sent_data_schema.safeParse(raw_data);
    const data = handle_parse_server_stats_result(result);
    if (data === undefined) {
        return;
    }

    type PiePlotData = {
        values: number[];
        labels: string[];
        total_html: string;
    };

    function make_plot_data(
        data: OrderedSentData,
        time_series_data: Record<string, number[]>,
        num_steps: number,
    ): PiePlotData {
        const plot_data = compute_summary_chart_data(
            time_series_data,
            num_steps,
            data.display_order,
        );
        const labels: string[] = [];
        for (let i = 0; i < plot_data.labels.length; i += 1) {
            labels.push(plot_data.labels[i] + " (" + plot_data.percentages[i] + ")");
        }
        const total_string = plot_data.total.toLocaleString();
        return {
            values: plot_data.values,
            labels,
            total_html: $t_html(
                {defaultMessage: "<b>Total messages</b>: {total_messages}"},
                {total_messages: total_string},
            ),
        };
    }

    const plot_data: DataByEveryoneUser<DataByTime<PiePlotData>> = {
        everyone: {
            cumulative: make_plot_data(data, data.everyone, data.end_times.length),
            year: make_plot_data(data, data.everyone, 365),
            month: make_plot_data(data, data.everyone, 30),
            week: make_plot_data(data, data.everyone, 7),
        },
        user: {
            cumulative: make_plot_data(data, data.user, data.end_times.length),
            year: make_plot_data(data, data.user, 365),
            month: make_plot_data(data, data.user, 30),
            week: make_plot_data(data, data.user, 7),
        },
    };

    let user_button: "everyone" | "user" = "everyone";
    let time_button: "cumulative" | "year" | "month" | "week";
    if (data.end_times.length >= 30) {
        time_button = "month";
        $("#messages_by_type_last_month_button").addClass("selected");
    } else {
        time_button = "cumulative";
        $("#messages_by_type_cumulative_button").addClass("selected");
    }
    const totaldiv = document.querySelector("#pie_messages_sent_by_type_total")!;

    if (data.end_times.length < 365) {
        $("#pie_messages_sent_by_type button[data-time='year']").remove();
        if (data.end_times.length < 30) {
            $("#pie_messages_sent_by_type button[data-time='month']").remove();
            if (data.end_times.length < 7) {
                $("#pie_messages_sent_by_type button[data-time='week']").remove();
            }
        }
    }

    const ctx = create_chart_canvas("id_messages_sent_by_message_type");
    const dataset: ChartDataset<"pie", number[]> = {data: [], backgroundColor: []};
    const chart = new Chart<"pie", number[], string>(ctx, {
        type: "pie",
        data: {labels: [], datasets: [dataset]},
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {position: "left", labels: {font: {size: legend_font_size}}},
            },
        },
    });

    function draw_plot(): void {
        const data_ = plot_data[user_button][time_button];
        chart.data.labels = data_.labels;
        dataset.data = data_.values;
        dataset.backgroundColor = data_.values.map((_, i) => pie_colors[i % pie_colors.length]!);
        chart.update();
        totaldiv.innerHTML = data_.total_html;
    }

    draw_plot();

    // Click handlers
    function set_user_button($button: JQuery): void {
        $("#pie_messages_sent_by_type button[data-user]").removeClass("selected");
        $button.addClass("selected");
    }

    function set_time_button($button: JQuery): void {
        $("#pie_messages_sent_by_type button[data-time]").removeClass("selected");
        $button.addClass("selected");
    }

    $("#pie_messages_sent_by_type button").on("click", function () {
        if ($(this).attr("data-user")) {
            set_user_button($(this));
            user_button = user_button_schema.parse($(this).attr("data-user"));
            // Now `user_button` will be of type "everyone" | "user"
        }
        if ($(this).attr("data-time")) {
            set_time_button($(this));
            time_button = time_button_schema.parse($(this).attr("data-time"));
            // Now `time_button` will be of type "cumulative" | "year" | "month" | "week"
        }
        draw_plot();
    });
}

function populate_number_of_users(raw_data: unknown): void {
    // Content rendered by this method is titled as "Active users" on the webpage
    const result = user_count_data_schema.safeParse(raw_data);
    const data = handle_parse_server_stats_result(result);
    if (data === undefined) {
        return;
    }

    const end_dates = data.end_times.map((timestamp: number) => new Date(timestamp * 1000));
    const hover_text = end_dates.map((date) => format_date(date, false));

    const ctx = create_chart_canvas("id_number_of_users");
    const active_users_label = $t({defaultMessage: "Active users"});
    let chart: ChartInstance<"bar" | "line", number[], Date> | undefined;

    function make_dataset(
        values: number[],
        type: "bar" | "line",
    ): ChartDataset<"bar" | "line", number[]> {
        if (type === "line") {
            return {
                type: "line",
                label: active_users_label,
                data: values,
                borderColor: color_humans,
                backgroundColor: color_humans,
                pointRadius: 0,
            } satisfies ChartDataset<"line", number[]>;
        }
        return {
            type: "bar",
            label: active_users_label,
            data: values,
            backgroundColor: color_humans,
        } satisfies ChartDataset<"bar", number[]>;
    }

    function draw_plot(values: number[], type: "bar" | "line"): void {
        const dataset = make_dataset(values, type);
        if (chart === undefined) {
            chart = new Chart<"bar" | "line", number[], Date>(ctx, {
                type: "bar",
                data: {labels: end_dates, datasets: [dataset]},
                // All views are daily data, so the default minimum tick step
                // of one day is fine.
                options: time_series_options(false, () => 1),
            });
            attach_time_series_interactions(
                chart,
                "users_hover_info",
                "users_hover_date",
                () => hover_text,
                [{dataset_index: 0, label_id: undefined, value_id: "users_hover_1day_value"}],
            );
        } else {
            // Keep the current zoom/pan range when switching views.
            chart.data.datasets = [dataset];
            chart.update();
        }
    }

    $("#1day_actives_button").on("click", function () {
        draw_plot(data.everyone._1day, "bar");
        $("#1day_actives_button, #15day_actives_button, #all_time_actives_button").removeClass(
            "selected",
        );
        $(this).addClass("selected");
    });

    $("#15day_actives_button").on("click", function () {
        draw_plot(data.everyone._15day, "line");
        $("#1day_actives_button, #15day_actives_button, #all_time_actives_button").removeClass(
            "selected",
        );
        $(this).addClass("selected");
    });

    $("#all_time_actives_button").on("click", function () {
        draw_plot(data.everyone.all_time, "line");
        $("#1day_actives_button, #15day_actives_button, #all_time_actives_button").removeClass(
            "selected",
        );
        $(this).addClass("selected");
    });

    // Initial drawing of plot
    draw_plot(data.everyone.all_time, "line");
    $("#all_time_actives_button").addClass("selected");
    get_user_summary_statistics(data.everyone);
}

function populate_messages_read_over_time(raw_data: unknown): void {
    // Content rendered by this method is titled as "Messages read over time" on the webpage
    const result = read_data_schema.safeParse(raw_data);
    const data = handle_parse_server_stats_result(result);
    if (data === undefined) {
        return;
    }

    if (data.end_times.length === 0) {
        // TODO: do something nicer here
        return;
    }

    const start_dates = data.end_times.map(
        (timestamp: number) =>
            // data.end_times are the ends of hour long intervals.
            new Date(timestamp * 1000 - 60 * 60 * 1000),
    );

    function aggregate_data(
        data: ReadData,
        aggregation: "day" | "week",
    ): AggregatedData<DataByEveryoneMe<number[]>> {
        let start;
        let is_boundary;
        if (aggregation === "day") {
            start = floor_to_local_day(start_dates[0]!);
            is_boundary = function (date: Date) {
                return date.getHours() === 0;
            };
        } else {
            assert(aggregation === "week");
            start = floor_to_local_week(start_dates[0]!);
            is_boundary = function (date: Date) {
                return date.getHours() === 0 && date.getDay() === 0;
            };
        }
        const dates = [start];
        const values: DataByEveryoneMe<number[]> = {everyone: [], me: []};
        let current: DataByEveryoneMe<number> = {everyone: 0, me: 0};
        let i_init = 0;
        if (is_boundary(start_dates[0]!)) {
            current = {everyone: data.everyone.read[0]!, me: data.user.read[0]!};
            i_init = 1;
        }
        for (let i = i_init; i < start_dates.length; i += 1) {
            if (is_boundary(start_dates[i]!)) {
                dates.push(start_dates[i]!);
                values.everyone.push(current.everyone);
                values.me.push(current.me);
                current = {everyone: 0, me: 0};
            }
            current.everyone += data.everyone.read[i]!;
            current.me += data.user.read[i]!;
        }
        values.everyone.push(current.everyone);
        values.me.push(current.me);
        return {
            dates,
            values,
            last_value_is_partial: !is_boundary(
                new Date(start_dates.at(-1)!.getTime() + 60 * 60 * 1000),
            ),
        };
    }

    // Build the three views. The series order is [me, everyone] to match the
    // dataset order created below.
    function make_view(
        dates: Date[],
        values: DataByEveryoneMe<number[]>,
        type: "bar" | "line",
        last_value_is_partial: boolean,
        min_step_days: number,
        date_formatter: DateFormatter,
    ): ChartView {
        return {
            times: dates,
            hover_text: dates.map((date) => date_formatter(date)),
            type,
            min_step_days,
            series: [
                {
                    data: values.me,
                    color: color_me,
                    bar_colors: bar_backgrounds(color_me, values.me.length, last_value_is_partial),
                },
                {
                    data: values.everyone,
                    color: color_everyone,
                    bar_colors: bar_backgrounds(
                        color_everyone,
                        values.everyone.length,
                        last_value_is_partial,
                    ),
                },
            ],
        };
    }

    const daily_info = aggregate_data(data, "day");
    const daily_view = make_view(daily_info.dates, daily_info.values, "bar", true, 1, (date) =>
        format_date(date, false),
    );

    const weekly_info = aggregate_data(data, "week");
    const weekly_view = make_view(weekly_info.dates, weekly_info.values, "bar", true, 7, (date) =>
        $t({defaultMessage: "Week of {date}"}, {date: format_date(date, false)}),
    );

    const cumulative_dates = data.end_times.map((timestamp: number) => new Date(timestamp * 1000));
    const cumulative_values = {
        me: partial_sums(data.user.read),
        everyone: partial_sums(data.everyone.read),
    };
    const cumulative_view = make_view(
        cumulative_dates,
        cumulative_values,
        "line",
        false,
        1,
        (date) => format_date(date, true),
    );

    const ctx = create_chart_canvas("id_messages_read_over_time");
    const series_names = [$t({defaultMessage: "Me"}), $t({defaultMessage: "Everyone"})];
    // Default visibility: only "Everyone" is shown; "Me" starts hidden but can
    // be toggled on from the legend.
    const default_hidden = [true, false];

    let current_hover_text: string[] = [];
    let current_min_step_days = 1;
    let chart: ChartInstance<"bar" | "line", number[], Date> | undefined;

    function draw_plot(view: ChartView): void {
        current_hover_text = view.hover_text;
        current_min_step_days = view.min_step_days;
        const hidden =
            chart === undefined
                ? default_hidden
                : series_names.map((_, i) => !chart!.isDatasetVisible(i));
        const datasets = build_time_series_datasets(view, series_names, hidden);
        if (chart === undefined) {
            chart = new Chart<"bar" | "line", number[], Date>(ctx, {
                type: "bar",
                data: {labels: view.times, datasets},
                options: time_series_options(true, () => current_min_step_days),
            });
            attach_time_series_interactions(
                chart,
                "read_hover_info",
                "read_hover_date",
                () => current_hover_text,
                [
                    {dataset_index: 0, label_id: "read_hover_me", value_id: "read_hover_me_value"},
                    {
                        dataset_index: 1,
                        label_id: "read_hover_everyone",
                        value_id: "read_hover_everyone_value",
                    },
                ],
            );
        } else {
            // Keep the current zoom/pan range when switching daily/weekly/
            // cumulative views.
            chart.data.labels = view.times;
            chart.data.datasets = datasets;
            chart.update();
        }
    }

    $("#read_daily_button").on("click", function () {
        draw_plot(daily_view);
        $("#read_daily_button, #read_weekly_button, #read_cumulative_button").removeClass(
            "selected",
        );
        $(this).addClass("selected");
    });

    $("#read_weekly_button").on("click", function () {
        draw_plot(weekly_view);
        $("#read_daily_button, #read_weekly_button, #read_cumulative_button").removeClass(
            "selected",
        );
        $(this).addClass("selected");
    });

    $("#read_cumulative_button").on("click", function () {
        draw_plot(cumulative_view);
        $("#read_daily_button, #read_weekly_button, #read_cumulative_button").removeClass(
            "selected",
        );
        $(this).addClass("selected");
    });

    // Initial drawing of plot
    if (weekly_view.times.length < 12) {
        draw_plot(daily_view);
        $("#read_daily_button").addClass("selected");
    } else {
        draw_plot(weekly_view);
        $("#read_weekly_button").addClass("selected");
    }
}

// Above are helper functions that prepare the plot data
// Below are main functions that render the plots

function get_chart_data(
    data: {
        chart_name: string;
        min_length: string;
    },
    callback: (data: unknown) => void,
): void {
    void $.get({
        url: "/json/analytics/chart_data" + page_params.data_url_suffix,
        data,
        success(data) {
            callback(data);
            const {end_times} = z.object({end_times: z.array(z.number())}).parse(data);
            update_last_full_update(end_times);
        },
        error(xhr) {
            const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
            if (parsed.success) {
                $("#id_stats_errors").show().text(parsed.data.msg);
            }
        },
    });
}

get_chart_data(
    {chart_name: "messages_sent_over_time", min_length: "10"},
    populate_messages_sent_over_time,
);

get_chart_data(
    {chart_name: "messages_sent_by_client", min_length: "10"},
    populate_messages_sent_by_client,
);

get_chart_data(
    {chart_name: "messages_sent_by_message_type", min_length: "10"},
    populate_messages_sent_by_message_type,
);

get_chart_data({chart_name: "number_of_humans", min_length: "10"}, populate_number_of_users);

get_chart_data(
    {chart_name: "messages_read_over_time", min_length: "10"},
    populate_messages_read_over_time,
);

set_storage_space_used_statistic(page_params.upload_space_used);
set_guest_users_statistic(page_params.guest_users);

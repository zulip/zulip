import $ from "jquery";
import assert from "minimalistic-assert";
import PlotlyBar from "plotly.js/lib/bar";
import Plotly from "plotly.js/lib/core";
import PlotlyPie from "plotly.js/lib/pie";
import tippy from "tippy.js";
import {z} from "zod";

import * as blueslip from "../blueslip";
import {$t, $t_html} from "../i18n";

import {page_params} from "./page_params";

Plotly.register([PlotlyBar, PlotlyPie]);

// Define types
type DateFormatter = (date: Date) => string;

type AggregatedData<T> = {
    dates: Date[];
    values: T;
    last_value_is_partial: boolean;
};

// Partial used here because the @types/plotly.js define the full
// set of properties while we only assign several of them.
type PlotTrace = {
    trace: Partial<Plotly.PlotData>;
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

// Define zod schemas for plotly
const datum_schema: z.ZodType<Plotly.Datum> = z.any();

// Define a schema factory function for the utility generic type
// The inferred types from zod have to be used to type the return values
// eslint-disable-next-line @typescript-eslint/explicit-function-return-type
function instantiate_type_DataByEveryoneUser<T extends z.ZodTypeAny>(schema: T) {
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

const read_data_schema = instantiate_type_DataByEveryoneUser(
    z.object({read: z.array(z.number())}),
).extend({...common_data_schema.shape});

const sent_data_schema = instantiate_type_DataByEveryoneUser(z.record(z.array(z.number()))).extend({
    ...common_data_schema.shape,
});
const ordered_sent_data_schema = sent_data_schema.extend({display_order: z.array(z.string())});

const user_count_data_schema = z
    .object({everyone: active_user_data})
    .extend({...common_data_schema.shape});

// Inferred types used in nested functions
type SentData = z.infer<typeof sent_data_schema>;
type OrderedSentData = z.infer<typeof ordered_sent_data_schema>;
type ReadData = z.infer<typeof read_data_schema>;

// Define misc zod schemas
const time_button_schema = z.enum(["cumulative", "year", "month", "week"]);
const user_button_schema = z.enum(["everyone", "user"]);

const font_14pt = {
    family: "Open Sans, sans-serif",
    size: 14,
    color: "#000000",
};

const font_12pt = {
    family: "Open Sans, sans-serif",
    size: 12,
    color: "#000000",
};

let last_full_update = Number.POSITIVE_INFINITY;

function handle_parse_server_stats_result<_, T>(
    result: z.SafeParseReturnType<_, T>,
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
    const date_copy = new Date(date.getTime());
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
    tippy(".last_update_tooltip", {
        // Same defaults as set in our tippyjs module.
        maxWidth: 300,
        delay: [100, 20],
        animation: false,
        touch: ["hold", 750],
        placement: "top",
    });
    // Add configuration for any additional tooltips here.
});

// Helper used in vertical bar charts
function make_rangeselector(
    button1: Partial<Plotly.RangeSelectorButton>,
    button2: Partial<Plotly.RangeSelectorButton>,
): Partial<Plotly.RangeSelector> {
    return {
        x: -0.045,
        y: -0.62,
        buttons: [
            {stepmode: "backward", ...button1},
            {stepmode: "backward", ...button2},
            {step: "all", label: $t({defaultMessage: "All time"})},
        ],
    };
}

type ActiveUserData = {
    _1day: Plotly.Datum[];
    _15day: Plotly.Datum[];
    all_time: Plotly.Datum[];
};

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

// PLOTLY CHARTS
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

    // Helper functions
    function make_traces(
        dates: Date[],
        values: DataByUserType<number[]>,
        type: Plotly.PlotType,
        date_formatter: DateFormatter,
    ): DataByUserType<Partial<Plotly.PlotData>> {
        const text = dates.map((date) => date_formatter(date));
        const common: Partial<Plotly.PlotData> = {
            x: dates,
            type,
            hoverinfo: "none",
            text,
            textposition: "none",
        };
        return {
            human: {
                // 5062a0
                name: $t({defaultMessage: "Humans"}),
                y: values.human,
                marker: {color: "#5f6ea0"},
                ...common,
            },
            bot: {
                // a09b5f bbb56e
                name: $t({defaultMessage: "Bots"}),
                y: values.bot,
                marker: {color: "#b7b867"},
                ...common,
            },
            me: {
                name: $t({defaultMessage: "Me"}),
                y: values.me,
                marker: {color: "#be6d68"},
                ...common,
            },
        };
    }

    const layout: Partial<Plotly.Layout> = {
        barmode: "group",
        width: 750,
        height: 400,
        margin: {l: 40, r: 10, b: 40, t: 0},
        xaxis: {
            fixedrange: true,
            rangeslider: {bordercolor: "#D8D8D8", borderwidth: 1},
            type: "date",
            tickangle: 0,
        },
        yaxis: {fixedrange: true, rangemode: "tozero"},
        legend: {
            x: 0.62,
            y: 1.12,
            orientation: "h",
            font: font_14pt,
        },
        font: font_12pt,
    };

    // This is also the cumulative rangeselector
    const daily_rangeselector = make_rangeselector(
        {count: 10, label: $t({defaultMessage: "Last 10 days"}), step: "day"},
        {count: 30, label: $t({defaultMessage: "Last 30 days"}), step: "day"},
    );
    const weekly_rangeselector = make_rangeselector(
        {count: 2, label: $t({defaultMessage: "Last 2 months"}), step: "month"},
        {count: 6, label: $t({defaultMessage: "Last 6 months"}), step: "month"},
    );

    function add_hover_handler(): void {
        document
            .querySelector<Plotly.PlotlyHTMLElement>("#id_messages_sent_over_time")!
            .on("plotly_hover", (data) => {
                $("#hoverinfo").show();
                document.querySelector("#hover_date")!.textContent =
                    data.points[0].data.text[data.points[0].pointNumber];
                const values: Plotly.Datum[] = [null, null, null];
                for (const trace of data.points) {
                    values[trace.curveNumber] = trace.y;
                }
                const hover_text_ids = ["#hover_me", "#hover_human", "#hover_bot"];
                const hover_value_ids = [
                    "#hover_me_value",
                    "#hover_human_value",
                    "#hover_bot_value",
                ];
                for (const [i, value] of values.entries()) {
                    if (value !== null) {
                        document.querySelector<HTMLElement>(hover_text_ids[i])!.style.display =
                            "inline";
                        document.querySelector<HTMLElement>(hover_value_ids[i])!.style.display =
                            "inline";
                        document.querySelector<HTMLElement>(hover_value_ids[i])!.textContent =
                            value.toString();
                    } else {
                        document.querySelector<HTMLElement>(hover_text_ids[i])!.style.display =
                            "none";
                        document.querySelector<HTMLElement>(hover_value_ids[i])!.style.display =
                            "none";
                    }
                }
            });
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
            start = floor_to_local_day(start_dates[0]);
            is_boundary = function (date: Date) {
                return date.getHours() === 0;
            };
        } else {
            assert(aggregation === "week");
            start = floor_to_local_week(start_dates[0]);
            is_boundary = function (date: Date) {
                return date.getHours() === 0 && date.getDay() === 0;
            };
        }
        const dates = [start];
        const values: DataByUserType<number[]> = {human: [], bot: [], me: []};
        let current: DataByUserType<number> = {human: 0, bot: 0, me: 0};
        let i_init = 0;
        if (is_boundary(start_dates[0])) {
            current = {
                human: data.everyone.human[0],
                bot: data.everyone.bot[0],
                me: data.user.human[0],
            };
            i_init = 1;
        }
        for (let i = i_init; i < start_dates.length; i += 1) {
            if (is_boundary(start_dates[i])) {
                dates.push(start_dates[i]);
                values.human.push(current.human);
                values.bot.push(current.bot);
                values.me.push(current.me);
                current = {human: 0, bot: 0, me: 0};
            }
            current.human += data.everyone.human[i];
            current.bot += data.everyone.bot[i];
            current.me += data.user.human[i];
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

    // Generate traces
    let date_formatter = function (date: Date): string {
        return format_date(date, true);
    };
    let values = {me: data.user.human, human: data.everyone.human, bot: data.everyone.bot};

    let info = aggregate_data(data, "day");
    date_formatter = function (date) {
        return format_date(date, false);
    };
    const last_day_is_partial = info.last_value_is_partial;
    const daily_traces = make_traces(info.dates, info.values, "bar", date_formatter);
    get_thirty_days_messages_sent(info.values);

    info = aggregate_data(data, "week");
    date_formatter = function (date) {
        return $t({defaultMessage: "Week of {date}"}, {date: format_date(date, false)});
    };
    const last_week_is_partial = info.last_value_is_partial;
    const weekly_traces = make_traces(info.dates, info.values, "bar", date_formatter);

    const dates = data.end_times.map((timestamp: number) => new Date(timestamp * 1000));
    values = {
        human: partial_sums(data.everyone.human),
        bot: partial_sums(data.everyone.bot),
        me: partial_sums(data.user.human),
    };
    date_formatter = function (date) {
        return format_date(date, true);
    };
    get_total_messages_sent(values);
    const cumulative_traces = make_traces(dates, values, "scatter", date_formatter);

    // Functions to draw and interact with the plot

    // We need to redraw plot entirely if switching from (the cumulative) line
    // graph to any bar graph, since otherwise the rangeselector shows both (plotly bug)
    let clicked_cumulative = false;

    function draw_or_update_plot(
        rangeselector: Partial<Plotly.RangeSelector>,
        traces: DataByUserType<Partial<Plotly.PlotData>>,
        last_value_is_partial: boolean,
        initial_draw: boolean,
    ): void {
        $("#daily_button, #weekly_button, #cumulative_button").removeClass("selected");
        $("#id_messages_sent_over_time > div").removeClass("spinner");
        if (initial_draw) {
            traces.human.visible = true;
            traces.bot.visible = "legendonly";
            traces.me.visible = "legendonly";
        } else {
            const plotDiv = document.querySelector<Plotly.PlotlyHTMLElement>(
                "#id_messages_sent_over_time",
            )!;
            assert("visible" in plotDiv.data[0]);
            assert("visible" in plotDiv.data[1]);
            assert("visible" in plotDiv.data[2]);
            traces.me.visible = plotDiv.data[0].visible;
            traces.human.visible = plotDiv.data[1].visible;
            traces.bot.visible = plotDiv.data[2].visible;
        }
        layout.xaxis!.rangeselector = rangeselector;
        if (clicked_cumulative || initial_draw) {
            void Plotly.newPlot(
                "id_messages_sent_over_time",
                [traces.me, traces.human, traces.bot],
                layout,
                {displayModeBar: false},
            );
            add_hover_handler();
        } else {
            void Plotly.deleteTraces("id_messages_sent_over_time", [0, 1, 2]);
            void Plotly.addTraces("id_messages_sent_over_time", [
                traces.me,
                traces.human,
                traces.bot,
            ]);
            void Plotly.relayout("id_messages_sent_over_time", layout);
        }
        $("#id_messages_sent_over_time").attr(
            "last_value_is_partial",
            last_value_is_partial.toString(),
        );
    }

    // Click handlers for aggregation buttons
    $("#daily_button").on("click", function () {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $("#weekly_button").on("click", function () {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $("#cumulative_button").on("click", function () {
        clicked_cumulative = false;
        draw_or_update_plot(daily_rangeselector, cumulative_traces, false, false);
        $(this).addClass("selected");
        clicked_cumulative = true;
    });

    // Initial drawing of plot
    if (weekly_traces.human.x!.length < 12) {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, true);
        $("#daily_button").addClass("selected");
    } else {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, true);
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
    if (data.size !== 0) {
        labels[labels.length - 1] = "Other";
        for (const sum of data.values()) {
            values[labels.length - 1] += sum;
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

    type PlotDataByMessageClient = PlotTrace & {
        trace: {
            x: number[];
        };
        trace_annotations: Partial<Plotly.PlotData>;
    };

    const layout: Partial<Plotly.Layout> = {
        width: 750,
        height: undefined, // set in draw_plot()
        margin: {l: 10, r: 10, b: 40, t: 10},
        font: font_14pt,
        xaxis: {range: undefined}, // set in draw_plot()
        yaxis: {showticklabels: false},
        showlegend: false,
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
            label: everyone_month.labels[i],
            value: everyone_month.labels[i] === "Other" ? -1 : everyone_month.values[i],
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
    ): PlotDataByMessageClient {
        const plot_data = compute_summary_chart_data(time_series_data, num_steps, labels);
        plot_data.values.reverse();
        plot_data.labels.reverse();
        plot_data.percentages.reverse();
        const annotations: {values: number[]; labels: string[]; text: string[]} = {
            values: [],
            labels: [],
            text: [],
        };
        for (let i = 0; i < plot_data.values.length; i += 1) {
            if (plot_data.values[i] > 0) {
                annotations.values.push(plot_data.values[i]);
                annotations.labels.push(plot_data.labels[i]);
                annotations.text.push(
                    "   " + plot_data.labels[i] + " (" + plot_data.percentages[i] + ")",
                );
            }
        }
        return {
            trace: {
                x: plot_data.values,
                y: plot_data.labels,
                type: "bar",
                orientation: "h",
                textinfo: "text",
                hoverinfo: "none",
                marker: {color: "#537c5e"},
            },
            trace_annotations: {
                x: annotations.values,
                y: annotations.labels,
                mode: "text",
                type: "scatter",
                textposition: "middle right",
                text: annotations.text,
            },
        };
    }

    const plot_data: DataByEveryoneUser<DataByTime<PlotDataByMessageClient>> = {
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
        $("#pie_messages_sent_by_client button[data-time='year']").remove();
        if (data.end_times.length < 30) {
            $("#pie_messages_sent_by_client button[data-time='month']").remove();
            if (data.end_times.length < 7) {
                $("#pie_messages_sent_by_client button[data-time='week']").remove();
            }
        }
    }

    function draw_plot(): void {
        $("#id_messages_sent_by_client > div").removeClass("spinner");
        const data_ = plot_data[user_button][time_button];
        layout.height = layout.margin!.b! + data_.trace.x.length * 30;
        layout.xaxis!.range = [0, Math.max(...data_.trace.x) * 1.3];
        void Plotly.newPlot(
            "id_messages_sent_by_client",
            [data_.trace, data_.trace_annotations],
            layout,
            {displayModeBar: false, staticPlot: true},
        );
    }

    draw_plot();

    // Click handlers
    function set_user_button($button: JQuery): void {
        $("#pie_messages_sent_by_client button[data-user]").removeClass("selected");
        $button.addClass("selected");
    }

    function set_time_button($button: JQuery): void {
        $("#pie_messages_sent_by_client button[data-time]").removeClass("selected");
        $button.addClass("selected");
    }

    $("#pie_messages_sent_by_client button").on("click", function () {
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

    type PlotDataByMessageType = {
        trace: Partial<Plotly.PieData>;
        total_html: string;
    };

    const layout = {
        margin: {l: 90, r: 0, b: 10, t: 0},
        width: 750,
        height: 300,
        legend: {
            font: font_14pt,
        },
        font: font_12pt,
    };

    function make_plot_data(
        data: OrderedSentData,
        time_series_data: Record<string, number[]>,
        num_steps: number,
    ): PlotDataByMessageType {
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
            trace: {
                values: plot_data.values,
                labels,
                type: "pie",
                direction: "clockwise",
                rotation: -90,
                sort: false,
                textinfo: "text",
                text: plot_data.labels.map(() => ""),
                hoverinfo: "label+value",
                pull: 0.05,
                marker: {
                    colors: ["#68537c", "#be6d68", "#b3b348"],
                },
            },
            total_html: $t_html(
                {defaultMessage: "<b>Total messages</b>: {total_messages}"},
                {total_messages: total_string},
            ),
        };
    }

    const plot_data: DataByEveryoneUser<DataByTime<PlotDataByMessageType>> = {
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

    function draw_plot(): void {
        $("#id_messages_sent_by_message_type > div").removeClass("spinner");
        void Plotly.newPlot(
            "id_messages_sent_by_message_type",
            [plot_data[user_button][time_button].trace],
            layout,
            {displayModeBar: false},
        );
        totaldiv.innerHTML = plot_data[user_button][time_button].total_html;
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

    const weekly_rangeselector = make_rangeselector(
        {count: 2, label: $t({defaultMessage: "Last 2 months"}), step: "month"},
        {count: 6, label: $t({defaultMessage: "Last 6 months"}), step: "month"},
    );

    const layout: Partial<Plotly.Layout> = {
        width: 750,
        height: 370,
        margin: {l: 40, r: 10, b: 40, t: 0},
        xaxis: {
            fixedrange: true,
            rangeslider: {bordercolor: "#D8D8D8", borderwidth: 1},
            rangeselector: weekly_rangeselector,
            tickangle: 0,
        },
        yaxis: {fixedrange: true, rangemode: "tozero"},
        font: font_12pt,
    };

    const end_dates: Date[] = data.end_times.map((timestamp: number) => new Date(timestamp * 1000));

    const text = end_dates.map((date) => format_date(date, false));

    function make_traces(values: Plotly.Datum[], type: Plotly.PlotType): Partial<Plotly.PlotData> {
        return {
            x: end_dates,
            y: values,
            type,
            name: $t({defaultMessage: "Active users"}),
            hoverinfo: "none",
            text,
            visible: true,
        };
    }

    function add_hover_handler(): void {
        document
            .querySelector<Plotly.PlotlyHTMLElement>("#id_number_of_users")!
            .on("plotly_hover", (data) => {
                $("#users_hover_info").show();
                document.querySelector("#users_hover_date")!.textContent =
                    data.points[0].data.text[data.points[0].pointNumber];
                const values: Plotly.Datum[] = [null, null, null];
                for (const trace of data.points) {
                    values[trace.curveNumber] = trace.y;
                }
                const hover_value_ids = [
                    "#users_hover_1day_value",
                    "#users_hover_15day_value",
                    "#users_hover_all_time_value",
                ];
                for (const [i, value] of values.entries()) {
                    if (value !== null) {
                        document.querySelector<HTMLElement>(hover_value_ids[i])!.style.display =
                            "inline";
                        document.querySelector(hover_value_ids[i])!.textContent = value.toString();
                    } else {
                        document.querySelector<HTMLElement>(hover_value_ids[i])!.style.display =
                            "none";
                    }
                }
            });
    }

    const _1day_trace = make_traces(data.everyone._1day, "bar");
    const _15day_trace = make_traces(data.everyone._15day, "scatter");
    const all_time_trace = make_traces(data.everyone.all_time, "scatter");

    $("#id_number_of_users > div").removeClass("spinner");

    // Redraw the plot every time for simplicity. If we have perf problems with this in the
    // future, we can copy the update behavior from populate_messages_sent_over_time
    function draw_or_update_plot(trace: Plotly.Data): void {
        $("#1day_actives_button, #15day_actives_button, #all_time_actives_button").removeClass(
            "selected",
        );
        void Plotly.newPlot("id_number_of_users", [trace], layout, {displayModeBar: false});
        add_hover_handler();
    }

    $("#1day_actives_button").on("click", function () {
        draw_or_update_plot(_1day_trace);
        $(this).addClass("selected");
    });

    $("#15day_actives_button").on("click", function () {
        draw_or_update_plot(_15day_trace);
        $(this).addClass("selected");
    });

    $("#all_time_actives_button").on("click", function () {
        draw_or_update_plot(all_time_trace);
        $(this).addClass("selected");
    });

    // Initial drawing of plot
    draw_or_update_plot(all_time_trace);
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

    // Helper functions
    function make_traces(
        dates: Date[],
        values: DataByEveryoneMe<number[]>,
        type: Plotly.PlotType,
        date_formatter: DateFormatter,
    ): DataByEveryoneMe<Partial<Plotly.PlotData>> {
        const text = dates.map((date) => date_formatter(date));
        const common: Partial<Plotly.PlotData> = {
            x: dates,
            type,
            hoverinfo: "none",
            text,
            textposition: "none",
        };
        return {
            everyone: {
                name: $t({defaultMessage: "Everyone"}),
                y: values.everyone,
                marker: {color: "#5f6ea0"},
                ...common,
            },
            me: {
                name: $t({defaultMessage: "Me"}),
                y: values.me,
                marker: {color: "#be6d68"},
                ...common,
            },
        };
    }

    const layout: Partial<Plotly.Layout> = {
        barmode: "group",
        width: 750,
        height: 400,
        margin: {l: 40, r: 10, b: 40, t: 0},
        xaxis: {
            fixedrange: true,
            rangeslider: {bordercolor: "#D8D8D8", borderwidth: 1},
            type: "date",
            tickangle: 0,
        },
        yaxis: {fixedrange: true, rangemode: "tozero"},
        legend: {
            x: 0.62,
            y: 1.12,
            orientation: "h",
            font: font_14pt,
        },
        font: font_12pt,
    };

    // This is also the cumulative rangeselector
    const daily_rangeselector = make_rangeselector(
        {count: 10, label: $t({defaultMessage: "Last 10 days"}), step: "day"},
        {count: 30, label: $t({defaultMessage: "Last 30 days"}), step: "day"},
    );
    const weekly_rangeselector = make_rangeselector(
        {count: 2, label: $t({defaultMessage: "Last 2 months"}), step: "month"},
        {count: 6, label: $t({defaultMessage: "Last 6 months"}), step: "month"},
    );

    function add_hover_handler(): void {
        document
            .querySelector<Plotly.PlotlyHTMLElement>("#id_messages_read_over_time")!
            .on("plotly_hover", (data) => {
                $("#read_hover_info").show();
                document.querySelector("#read_hover_date")!.textContent =
                    data.points[0].data.text[data.points[0].pointNumber];
                const values: Plotly.Datum[] = [null, null];
                for (const trace of data.points) {
                    values[trace.curveNumber] = trace.y;
                }
                const read_hover_text_ids = ["#read_hover_me", "#read_hover_everyone"];
                const read_hover_value_ids = ["#read_hover_me_value", "#read_hover_everyone_value"];
                for (const [i, value] of values.entries()) {
                    if (value !== null) {
                        document.querySelector<HTMLElement>(read_hover_text_ids[i])!.style.display =
                            "inline";
                        document.querySelector<HTMLElement>(
                            read_hover_value_ids[i],
                        )!.style.display = "inline";
                        document.querySelector<HTMLElement>(read_hover_value_ids[i])!.textContent =
                            value.toString();
                    } else {
                        document.querySelector<HTMLElement>(read_hover_text_ids[i])!.style.display =
                            "none";
                        document.querySelector<HTMLElement>(
                            read_hover_value_ids[i],
                        )!.style.display = "none";
                    }
                }
            });
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
            start = floor_to_local_day(start_dates[0]);
            is_boundary = function (date: Date) {
                return date.getHours() === 0;
            };
        } else {
            assert(aggregation === "week");
            start = floor_to_local_week(start_dates[0]);
            is_boundary = function (date: Date) {
                return date.getHours() === 0 && date.getDay() === 0;
            };
        }
        const dates = [start];
        const values: DataByEveryoneMe<number[]> = {everyone: [], me: []};
        let current: DataByEveryoneMe<number> = {everyone: 0, me: 0};
        let i_init = 0;
        if (is_boundary(start_dates[0])) {
            current = {everyone: data.everyone.read[0], me: data.user.read[0]};
            i_init = 1;
        }
        for (let i = i_init; i < start_dates.length; i += 1) {
            if (is_boundary(start_dates[i])) {
                dates.push(start_dates[i]);
                values.everyone.push(current.everyone);
                values.me.push(current.me);
                current = {everyone: 0, me: 0};
            }
            current.everyone += data.everyone.read[i];
            current.me += data.user.read[i];
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

    // Generate traces
    let date_formatter = function (date: Date): string {
        return format_date(date, true);
    };
    let values = {me: data.user.read, everyone: data.everyone.read};

    let info = aggregate_data(data, "day");
    date_formatter = function (date) {
        return format_date(date, false);
    };
    const last_day_is_partial = info.last_value_is_partial;
    const daily_traces = make_traces(info.dates, info.values, "bar", date_formatter);

    info = aggregate_data(data, "week");
    date_formatter = function (date) {
        return $t({defaultMessage: "Week of {date}"}, {date: format_date(date, false)});
    };
    const last_week_is_partial = info.last_value_is_partial;
    const weekly_traces = make_traces(info.dates, info.values, "bar", date_formatter);

    const dates = data.end_times.map((timestamp: number) => new Date(timestamp * 1000));
    values = {everyone: partial_sums(data.everyone.read), me: partial_sums(data.user.read)};
    date_formatter = function (date) {
        return format_date(date, true);
    };
    const cumulative_traces = make_traces(dates, values, "scatter", date_formatter);

    // Functions to draw and interact with the plot

    // We need to redraw plot entirely if switching from (the cumulative) line
    // graph to any bar graph, since otherwise the rangeselector shows both (plotly bug)
    let clicked_cumulative = false;

    function draw_or_update_plot(
        rangeselector: Partial<Plotly.RangeSelector>,
        traces: DataByEveryoneMe<Partial<Plotly.PlotData>>,
        last_value_is_partial: boolean,
        initial_draw: boolean,
    ): void {
        $("#read_daily_button, #read_weekly_button, #read_cumulative_button").removeClass(
            "selected",
        );
        $("#id_messages_read_over_time > div").removeClass("spinner");
        if (initial_draw) {
            traces.everyone.visible = true;
            traces.me.visible = "legendonly";
        } else {
            const plotDiv = document.querySelector<Plotly.PlotlyHTMLElement>(
                "#id_messages_read_over_time",
            )!;
            assert("visible" in plotDiv.data[0]);
            assert("visible" in plotDiv.data[1]);
            traces.me.visible = plotDiv.data[0].visible;
            traces.everyone.visible = plotDiv.data[1].visible;
        }
        layout.xaxis!.rangeselector = rangeselector;
        if (clicked_cumulative || initial_draw) {
            void Plotly.newPlot(
                "id_messages_read_over_time",
                [traces.me, traces.everyone],
                layout,
                {
                    displayModeBar: false,
                },
            );
            add_hover_handler();
        } else {
            void Plotly.deleteTraces("id_messages_read_over_time", [0, 1]);
            void Plotly.addTraces("id_messages_read_over_time", [traces.me, traces.everyone]);
            void Plotly.relayout("id_messages_read_over_time", layout);
        }
        $("#id_messages_read_over_time").attr(
            "last_value_is_partial",
            last_value_is_partial.toString(),
        );
    }

    // Click handlers for aggregation buttons
    $("#read_daily_button").on("click", function () {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $("#read_weekly_button").on("click", function () {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $("#read_cumulative_button").on("click", function () {
        clicked_cumulative = false;
        draw_or_update_plot(daily_rangeselector, cumulative_traces, false, false);
        $(this).addClass("selected");
        clicked_cumulative = true;
    });

    // Initial drawing of plot
    if (weekly_traces.everyone.x!.length < 12) {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, true);
        $("#read_daily_button").addClass("selected");
    } else {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, true);
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

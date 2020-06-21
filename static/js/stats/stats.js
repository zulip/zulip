const font_14pt = {
    family: 'Source Sans Pro',
    size: 14,
    color: '#000000',
};

let last_full_update = Infinity;

// TODO: should take a dict of arrays and do it for all keys
function partial_sums(array) {
    let accumulator = 0;
    return array.map(function (o) {
        accumulator += o;
        return accumulator;
    });
}

// Assumes date is a round number of hours
function floor_to_local_day(date) {
    const date_copy = new Date(date.getTime());
    date_copy.setHours(0);
    return date_copy;
}

// Assumes date is a round number of hours
function floor_to_local_week(date) {
    const date_copy = floor_to_local_day(date);
    date_copy.setHours(-24 * date.getDay());
    return date_copy;
}

function format_date(date, include_hour) {
    const months = [
        i18n.t('January'),
        i18n.t('February'),
        i18n.t('March'),
        i18n.t('April'),
        i18n.t('May'),
        i18n.t('June'),
        i18n.t('July'),
        i18n.t('August'),
        i18n.t('September'),
        i18n.t('October'),
        i18n.t('November'),
        i18n.t('December'),
    ];
    const month_str = months[date.getMonth()];
    const year = date.getFullYear();
    const day = date.getDate();
    if (include_hour) {
        const hour = date.getHours();

        const str = hour >= 12 ? "PM" : "AM";

        return month_str + " " + day + ", " + hour % 12 + ":00" + str;
    }
    return month_str + ' ' + day + ', ' + year;
}

function update_last_full_update(end_times) {
    if (end_times.length === 0) {
        return;
    }

    last_full_update = Math.min(last_full_update, end_times[end_times.length - 1]);
    const update_time = new Date(last_full_update * 1000);
    const locale_date = update_time.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    const locale_time = update_time.toLocaleTimeString().replace(":00 ", " ");

    $('#id_last_full_update').text(locale_time + " on " + locale_date);
    $('#id_last_full_update').closest('.last-update').show();
}

$(function tooltips() {
    $('span[data-toggle="tooltip"]').tooltip({
        animation: false,
        placement: 'top',
        trigger: 'manual',
    });
    $('#id_last_update_question_sign').hover(function () {
        $('span.last_update_tooltip').tooltip('toggle');
    });
    // Add configuration for any additional tooltips here.
});

function populate_messages_sent_over_time(data) {
    if (data.end_times.length === 0) {
        // TODO: do something nicer here
        return;
    }

    // Helper functions
    function make_traces(dates, values, type, date_formatter) {
        const text = dates.map(function (date) {
            return date_formatter(date);
        });
        const common = { x: dates, type: type, hoverinfo: 'none', text: text };
        return {
            human: { // 5062a0
                name: i18n.t("Humans"), y: values.human, marker: {color: '#5f6ea0'},
                ...common,
            },
            bot: { // a09b5f bbb56e
                name: i18n.t("Bots"), y: values.bot, marker: {color: '#b7b867'},
                ...common,
            },
            me: {
                name: i18n.t("Me"), y: values.me, marker: {color: '#be6d68'},
                ...common,
            },
        };
    }

    const layout = {
        barmode: 'group',
        width: 750,
        height: 400,
        margin: { l: 40, r: 0, b: 40, t: 0 },
        xaxis: {
            fixedrange: true,
            rangeslider: { bordercolor: '#D8D8D8', borderwidth: 1 },
            type: 'date',
        },
        yaxis: { fixedrange: true, rangemode: 'tozero' },
        legend: {
            x: 0.62, y: 1.12, orientation: 'h', font: font_14pt,
        },
        font: font_14pt,
    };

    function make_rangeselector(x, y, button1, button2) {
        return {x: x, y: y,
                buttons: [
                    {stepmode: 'backward', ...button1},
                    {stepmode: 'backward', ...button2},
                    {step: 'all', label: 'All time'}]};
    }

    // This is also the cumulative rangeselector
    const daily_rangeselector = make_rangeselector(
        0.68, -0.62,
        {count: 10, label: i18n.t('Last 10 days'), step: 'day'},
        {count: 30, label: i18n.t('Last 30 days'), step: 'day'});
    const weekly_rangeselector = make_rangeselector(
        0.656, -0.62,
        {count: 2, label: i18n.t('Last 2 months'), step: 'month'},
        {count: 6, label: i18n.t('Last 6 months'), step: 'month'});

    function add_hover_handler() {
        document.getElementById('id_messages_sent_over_time').on('plotly_hover', function (data) {
            $("#hoverinfo").show();
            document.getElementById('hover_date').innerText =
                data.points[0].data.text[data.points[0].pointNumber];
            const values = [null, null, null];
            data.points.forEach(function (trace) {
                values[trace.curveNumber] = trace.y;
            });
            const hover_text_ids = ['hover_me', 'hover_human', 'hover_bot'];
            const hover_value_ids = ['hover_me_value', 'hover_human_value', 'hover_bot_value'];
            for (let i = 0; i < values.length; i += 1) {
                if (values[i] !== null) {
                    document.getElementById(hover_text_ids[i]).style.display = 'inline';
                    document.getElementById(hover_value_ids[i]).style.display = 'inline';
                    document.getElementById(hover_value_ids[i]).innerText = values[i];
                } else {
                    document.getElementById(hover_text_ids[i]).style.display = 'none';
                    document.getElementById(hover_value_ids[i]).style.display = 'none';
                }
            }
        });
    }

    const start_dates = data.end_times.map(function (timestamp) {
        // data.end_times are the ends of hour long intervals.
        return new Date(timestamp * 1000 - 60 * 60 * 1000);
    });

    function aggregate_data(aggregation) {
        let start;
        let is_boundary;
        if (aggregation === 'day') {
            start = floor_to_local_day(start_dates[0]);
            is_boundary = function (date) {
                return date.getHours() === 0;
            };
        } else if (aggregation === 'week') {
            start = floor_to_local_week(start_dates[0]);
            is_boundary = function (date) {
                return date.getHours() === 0 && date.getDay() === 0;
            };
        }
        const dates = [start];
        const values = {human: [], bot: [], me: []};
        let current = {human: 0, bot: 0, me: 0};
        let i_init = 0;
        if (is_boundary(start_dates[0])) {
            current = {human: data.everyone.human[0],
                       bot: data.everyone.bot[0],
                       me: data.user.human[0]};
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
            dates: dates, values: values,
            last_value_is_partial: !is_boundary(new Date(
                start_dates[start_dates.length - 1].getTime() + 60 * 60 * 1000))};
    }

    // Generate traces
    let date_formatter = function (date) {
        return format_date(date, true);
    };
    let values = {me: data.user.human, human: data.everyone.human, bot: data.everyone.bot};

    let info = aggregate_data('day');
    date_formatter = function (date) {
        return format_date(date, false);
    };
    const last_day_is_partial = info.last_value_is_partial;
    const daily_traces = make_traces(info.dates, info.values, 'bar', date_formatter);

    info = aggregate_data('week');
    date_formatter = function (date) {
        return i18n.t("Week of __date__", {date: format_date(date, false)});
    };
    const last_week_is_partial = info.last_value_is_partial;
    const weekly_traces = make_traces(info.dates, info.values, 'bar', date_formatter);

    const dates = data.end_times.map(function (timestamp) {
        return new Date(timestamp * 1000);
    });
    values = {human: partial_sums(data.everyone.human), bot: partial_sums(data.everyone.bot),
              me: partial_sums(data.user.human)};
    date_formatter = function (date) {
        return format_date(date, true);
    };
    const cumulative_traces = make_traces(dates, values, 'scatter', date_formatter);

    // Functions to draw and interact with the plot

    // We need to redraw plot entirely if switching from (the cumulative) line
    // graph to any bar graph, since otherwise the rangeselector shows both (plotly bug)
    let clicked_cumulative = false;

    function draw_or_update_plot(rangeselector, traces, last_value_is_partial, initial_draw) {
        $('#daily_button, #weekly_button, #cumulative_button').removeClass("selected");
        $('#id_messages_sent_over_time > div').removeClass("spinner");
        if (initial_draw) {
            traces.human.visible = true;
            traces.bot.visible = 'legendonly';
            traces.me.visible = 'legendonly';
        } else {
            const plotDiv = document.getElementById('id_messages_sent_over_time');
            traces.me.visible = plotDiv.data[0].visible;
            traces.human.visible = plotDiv.data[1].visible;
            traces.bot.visible = plotDiv.data[2].visible;
        }
        layout.xaxis.rangeselector = rangeselector;
        if (clicked_cumulative || initial_draw) {
            Plotly.newPlot('id_messages_sent_over_time',
                           [traces.me, traces.human, traces.bot], layout, {displayModeBar: false});
            add_hover_handler();
        } else {
            Plotly.deleteTraces('id_messages_sent_over_time', [0, 1, 2]);
            Plotly.addTraces('id_messages_sent_over_time', [traces.me, traces.human, traces.bot]);
            Plotly.relayout('id_messages_sent_over_time', layout);
        }
        $('#id_messages_sent_over_time').attr('last_value_is_partial', last_value_is_partial);
    }

    // Click handlers for aggregation buttons
    $('#daily_button').click(function () {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $('#weekly_button').click(function () {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $('#cumulative_button').click(function () {
        clicked_cumulative = false;
        draw_or_update_plot(daily_rangeselector, cumulative_traces, false, false);
        $(this).addClass("selected");
        clicked_cumulative = true;
    });

    // Initial drawing of plot
    if (weekly_traces.human.x.length < 12) {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, true);
        $('#daily_button').addClass("selected");
    } else {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, true);
        $('#weekly_button').addClass("selected");
    }
}

function round_to_percentages(values, total) {
    return values.map(function (x) {
        if (x === total) {
            return '100%';
        }
        if (x === 0) {
            return '0%';
        }
        const unrounded = x / total * 100;

        const precision = Math.min(
            6, // this is the max precision (two #, 4 decimal points; 99.9999%).
            Math.max(
                2, // the minimum amount of precision (40% or 6.0%).
                Math.floor(-Math.log10(100 - unrounded)) + 3
            )
        );

        return unrounded.toPrecision(precision) + '%';
    });
}

// Last label will turn into "Other" if time_series data has a label not in labels
function compute_summary_chart_data(time_series_data, num_steps, labels_) {
    const data = new Map();
    for (const [key, array] of Object.entries(time_series_data)) {
        if (array.length < num_steps) {
            num_steps = array.length;
        }
        let sum = 0;
        for (let i = 1; i <= num_steps; i += 1) {
            sum += array[array.length - i];
        }
        data.set(key, sum);
    }
    const labels = labels_.slice();
    const values = [];
    labels.forEach(function (label) {
        if (data.has(label)) {
            values.push(data.get(label));
            data.delete(label);
        } else {
            values.push(0);
        }
    });
    if (data.size !== 0) {
        labels[labels.length - 1] = "Other";
        for (const sum of data.values()) {
            values[labels.length - 1] += sum;
        }
    }
    const total = values.reduce(function (a, b) { return a + b; }, 0);
    return {
        values: values,
        labels: labels,
        percentages: round_to_percentages(values, total),
        total: total,
    };
}

function populate_messages_sent_by_client(data) {
    const layout = {
        width: 750,
        height: null, // set in draw_plot()
        margin: { l: 3, r: 40, b: 40, t: 0 },
        font: font_14pt,
        xaxis: { range: null }, // set in draw_plot()
        yaxis: { showticklabels: false },
        showlegend: false,
    };

    // sort labels so that values are descending in the default view
    const everyone_month = compute_summary_chart_data(
        data.everyone, 30, data.display_order.slice(0, 12));
    const label_values = [];
    for (let i = 0; i < everyone_month.values.length; i += 1) {
        label_values.push({
            label: everyone_month.labels[i],
            value: everyone_month.labels[i] === "Other" ? -1 : everyone_month.values[i],
        });
    }
    label_values.sort(function (a, b) { return b.value - a.value; });
    const labels = [];
    label_values.forEach(function (item) { labels.push(item.label); });

    function make_plot_data(time_series_data, num_steps) {
        const plot_data = compute_summary_chart_data(time_series_data, num_steps, labels);
        plot_data.values.reverse();
        plot_data.labels.reverse();
        plot_data.percentages.reverse();
        const annotations = {values: [], labels: [], text: []};
        for (let i = 0; i < plot_data.values.length; i += 1) {
            if (plot_data.values[i] > 0) {
                annotations.values.push(plot_data.values[i]);
                annotations.labels.push(plot_data.labels[i]);
                annotations.text.push('   ' + plot_data.labels[i] + ' (' + plot_data.percentages[i] + ')');
            }
        }
        return {
            trace: {
                x: plot_data.values,
                y: plot_data.labels,
                type: 'bar',
                orientation: 'h',
                sort: false,
                textinfo: "text",
                hoverinfo: "none",
                marker: { color: '#537c5e' },
                font: { family: 'Source Sans Pro', size: 18, color: '#000000' },
            },
            trace_annotations: {
                x: annotations.values,
                y: annotations.labels,
                mode: 'text',
                type: 'scatter',
                textposition: 'middle right',
                text: annotations.text,
            },
        };
    }

    const plot_data = {
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

    let user_button = 'everyone';
    let time_button;
    if (data.end_times.length >= 30) {
        time_button = 'month';
        $('#messages_by_client_last_month_button').addClass("selected");
    } else {
        time_button = 'cumulative';
        $('#messages_by_client_cumulative_button').addClass("selected");
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

    function draw_plot() {
        $('#id_messages_sent_by_client > div').removeClass("spinner");
        const data_ = plot_data[user_button][time_button];
        layout.height = layout.margin.b + data_.trace.x.length * 30;
        layout.xaxis.range = [0, Math.max(...data_.trace.x) * 1.3];
        Plotly.newPlot('id_messages_sent_by_client',
                       [data_.trace, data_.trace_annotations],
                       layout,
                       {displayModeBar: false, staticPlot: true});
    }

    draw_plot();

    // Click handlers
    function set_user_button(button) {
        $("#pie_messages_sent_by_client button[data-user]").removeClass("selected");
        button.addClass("selected");
    }

    function set_time_button(button) {
        $("#pie_messages_sent_by_client button[data-time]").removeClass("selected");
        button.addClass("selected");
    }

    $("#pie_messages_sent_by_client button").click(function () {
        if ($(this).attr("data-user")) {
            set_user_button($(this));
            user_button = $(this).attr("data-user");
        }
        if ($(this).attr("data-time")) {
            set_time_button($(this));
            time_button = $(this).attr("data-time");
        }
        draw_plot();
    });

    // handle links with @href started with '#' only
    $(document).on('click', 'a[href^="#"]', function (e) {
        // target element id
        const id = $(this).attr('href');
        // target element
        const $id = $(id);
        if ($id.length === 0) {
            return;
        }
        // prevent standard hash navigation (avoid blinking in IE)
        e.preventDefault();
        const pos = $id.offset().top + $('.page-content')[0].scrollTop - 50;
        $('.page-content').animate({scrollTop: pos + "px"}, 500);
    });
}

function populate_messages_sent_by_message_type(data) {
    const layout = {
        margin: { l: 90, r: 0, b: 0, t: 0 },
        width: 750,
        height: 300,
        font: font_14pt,
    };

    function make_plot_data(time_series_data, num_steps) {
        const plot_data = compute_summary_chart_data(
            time_series_data,
            num_steps,
            data.display_order
        );
        const labels = [];
        for (let i = 0; i < plot_data.labels.length; i += 1) {
            labels.push(plot_data.labels[i] + ' (' + plot_data.percentages[i] + ')');
        }
        return {
            trace: {
                values: plot_data.values,
                labels: labels,
                type: 'pie',
                direction: 'clockwise',
                rotation: -90,
                sort: false,
                textinfo: "text",
                text: plot_data.labels.map(function () { return ''; }),
                hoverinfo: "label+value",
                pull: 0.05,
                marker: {
                    colors: ['#68537c', '#be6d68', '#b3b348'],
                },
            },
            total_str: "<b>Total messages:</b> " + plot_data.total.toString().
                replace(/\B(?=(\d{3})+(?!\d))/g, ","),
        };
    }

    const plot_data = {
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

    let user_button = 'everyone';
    let time_button;
    if (data.end_times.length >= 30) {
        time_button = 'month';
        $('#messages_by_type_last_month_button').addClass("selected");
    } else {
        time_button = 'cumulative';
        $('#messages_by_type_cumulative_button').addClass("selected");
    }
    const totaldiv = document.getElementById('pie_messages_sent_by_type_total');

    if (data.end_times.length < 365) {
        $("#pie_messages_sent_by_type button[data-time='year']").remove();
        if (data.end_times.length < 30) {
            $("#pie_messages_sent_by_type button[data-time='month']").remove();
            if (data.end_times.length < 7) {
                $("#pie_messages_sent_by_type button[data-time='week']").remove();
            }
        }
    }

    function draw_plot() {
        $('#id_messages_sent_by_message_type > div').removeClass("spinner");
        Plotly.newPlot('id_messages_sent_by_message_type',
                       [plot_data[user_button][time_button].trace],
                       layout,
                       {displayModeBar: false});
        totaldiv.innerHTML = plot_data[user_button][time_button].total_str;
    }

    draw_plot();

    // Click handlers
    function set_user_button(button) {
        $("#pie_messages_sent_by_type button[data-user]").removeClass("selected");
        button.addClass("selected");
    }

    function set_time_button(button) {
        $("#pie_messages_sent_by_type button[data-time]").removeClass("selected");
        button.addClass("selected");
    }

    $("#pie_messages_sent_by_type button").click(function () {
        if ($(this).attr("data-user")) {
            set_user_button($(this));
            user_button = $(this).attr("data-user");
        }
        if ($(this).attr("data-time")) {
            set_time_button($(this));
            time_button = $(this).attr("data-time");
        }
        draw_plot();
    });
}

function populate_number_of_users(data) {
    const layout = {
        width: 750,
        height: 370,
        margin: { l: 40, r: 0, b: 65, t: 20 },
        xaxis: {
            fixedrange: true,
            rangeslider: { bordercolor: '#D8D8D8', borderwidth: 1 },
            rangeselector: {
                x: 0.64, y: -0.79,
                buttons: [
                    { count: 2, label: i18n.t('Last 2 months'), step: 'month', stepmode: 'backward' },
                    { count: 6, label: i18n.t('Last 6 months'), step: 'month', stepmode: 'backward' },
                    { step: 'all', label: i18n.t('All time') },
                ]}},
        yaxis: { fixedrange: true, rangemode: 'tozero' },
        font: font_14pt,
    };

    const end_dates = data.end_times.map(function (timestamp) {
        return new Date(timestamp * 1000);
    });

    const text = end_dates.map(function (date) {
        return format_date(date, false);
    });

    function make_traces(values, type) {
        return {
            x: end_dates,
            y: values,
            type: type,
            name: i18n.t("Active users"),
            hoverinfo: 'none',
            text: text,
            visible: true,
        };
    }

    function add_hover_handler() {
        document.getElementById('id_number_of_users').on('plotly_hover', function (data) {
            $("#users_hover_info").show();
            document.getElementById('users_hover_date').innerText =
                data.points[0].data.text[data.points[0].pointNumber];
            const values = [null, null, null];
            data.points.forEach(function (trace) {
                values[trace.curveNumber] = trace.y;
            });
            const hover_value_ids = [
                'users_hover_1day_value', 'users_hover_15day_value', 'users_hover_all_time_value'];
            for (let i = 0; i < values.length; i += 1) {
                if (values[i] !== null) {
                    document.getElementById(hover_value_ids[i]).style.display = 'inline';
                    document.getElementById(hover_value_ids[i]).innerText = values[i];
                } else {
                    document.getElementById(hover_value_ids[i]).style.display = 'none';
                }
            }
        });
    }

    const _1day_trace = make_traces(data.everyone._1day, 'bar');
    const _15day_trace = make_traces(data.everyone._15day, 'scatter');
    const all_time_trace = make_traces(data.everyone.all_time, 'scatter');

    $('#id_number_of_users > div').removeClass("spinner");

    // Redraw the plot every time for simplicity. If we have perf problems with this in the
    // future, we can copy the update behavior from populate_messages_sent_over_time
    function draw_or_update_plot(trace) {
        $('#1day_actives_button, #15day_actives_button, #all_time_actives_button').removeClass("selected");
        Plotly.newPlot('id_number_of_users', [trace], layout, {displayModeBar: false});
        add_hover_handler();
    }

    $('#1day_actives_button').click(function () {
        draw_or_update_plot(_1day_trace);
        $(this).addClass("selected");
    });

    $('#15day_actives_button').click(function () {
        draw_or_update_plot(_15day_trace);
        $(this).addClass("selected");
    });

    $('#all_time_actives_button').click(function () {
        draw_or_update_plot(all_time_trace);
        $(this).addClass("selected");
    });

    // Initial drawing of plot
    draw_or_update_plot(all_time_trace, true);
    $('#all_time_actives_button').addClass("selected");
}

function populate_messages_read_over_time(data) {
    if (data.end_times.length === 0) {
        // TODO: do something nicer here
        return;
    }

    // Helper functions
    function make_traces(dates, values, type, date_formatter) {
        const text = dates.map(function (date) {
            return date_formatter(date);
        });
        const common = { x: dates, type: type, hoverinfo: 'none', text: text };
        return {
            everyone: {
                name: i18n.t("Everyone"), y: values.everyone, marker: {color: '#5f6ea0'},
                ...common,
            },
            me: {
                name: i18n.t("Me"), y: values.me, marker: {color: '#be6d68'},
                ...common,
            },
        };
    }

    const layout = {
        barmode: 'group',
        width: 750,
        height: 400,
        margin: { l: 40, r: 0, b: 40, t: 0 },
        xaxis: {
            fixedrange: true,
            rangeslider: { bordercolor: '#D8D8D8', borderwidth: 1 },
            type: 'date',
        },
        yaxis: { fixedrange: true, rangemode: 'tozero' },
        legend: {
            x: 0.62, y: 1.12, orientation: 'h', font: font_14pt,
        },
        font: font_14pt,
    };

    function make_rangeselector(x, y, button1, button2) {
        return {x: x, y: y,
                buttons: [
                    {stepmode: 'backward', ...button1},
                    {stepmode: 'backward', ...button2},
                    {step: 'all', label: 'All time'}]};
    }

    // This is also the cumulative rangeselector
    const daily_rangeselector = make_rangeselector(
        0.68, -0.62,
        {count: 10, label: i18n.t('Last 10 days'), step: 'day'},
        {count: 30, label: i18n.t('Last 30 days'), step: 'day'});
    const weekly_rangeselector = make_rangeselector(
        0.656, -0.62,
        {count: 2, label: i18n.t('Last 2 months'), step: 'month'},
        {count: 6, label: i18n.t('Last 6 months'), step: 'month'});

    function add_hover_handler() {
        document.getElementById('id_messages_read_over_time').on('plotly_hover', function (data) {
            $("#read_hover_info").show();
            document.getElementById('read_hover_date').innerText =
                data.points[0].data.text[data.points[0].pointNumber];
            const values = [null, null];
            data.points.forEach(function (trace) {
                values[trace.curveNumber] = trace.y;
            });
            const read_hover_text_ids = ['read_hover_me', 'read_hover_everyone'];
            const read_hover_value_ids = ['read_hover_me_value', 'read_hover_everyone_value'];
            for (let i = 0; i < values.length; i += 1) {
                if (values[i] !== null) {
                    document.getElementById(read_hover_text_ids[i]).style.display = 'inline';
                    document.getElementById(read_hover_value_ids[i]).style.display = 'inline';
                    document.getElementById(read_hover_value_ids[i]).innerText = values[i];
                } else {
                    document.getElementById(read_hover_text_ids[i]).style.display = 'none';
                    document.getElementById(read_hover_value_ids[i]).style.display = 'none';
                }
            }
        });
    }

    const start_dates = data.end_times.map(function (timestamp) {
        // data.end_times are the ends of hour long intervals.
        return new Date(timestamp * 1000 - 60 * 60 * 1000);
    });

    function aggregate_data(aggregation) {
        let start;
        let is_boundary;
        if (aggregation === 'day') {
            start = floor_to_local_day(start_dates[0]);
            is_boundary = function (date) {
                return date.getHours() === 0;
            };
        } else if (aggregation === 'week') {
            start = floor_to_local_week(start_dates[0]);
            is_boundary = function (date) {
                return date.getHours() === 0 && date.getDay() === 0;
            };
        }
        const dates = [start];
        const values = {everyone: [], me: []};
        let current = {everyone: 0, me: 0};
        let i_init = 0;
        if (is_boundary(start_dates[0])) {
            current = {everyone: data.everyone.read[0],
                       me: data.user.read[0]};
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
            dates: dates, values: values,
            last_value_is_partial: !is_boundary(new Date(
                start_dates[start_dates.length - 1].getTime() + 60 * 60 * 1000))};
    }

    // Generate traces
    let date_formatter = function (date) {
        return format_date(date, true);
    };
    let values = {me: data.user.read, everyone: data.everyone.read};

    let info = aggregate_data('day');
    date_formatter = function (date) {
        return format_date(date, false);
    };
    const last_day_is_partial = info.last_value_is_partial;
    const daily_traces = make_traces(info.dates, info.values, 'bar', date_formatter);

    info = aggregate_data('week');
    date_formatter = function (date) {
        return i18n.t("Week of __date__", {date: format_date(date, false)});
    };
    const last_week_is_partial = info.last_value_is_partial;
    const weekly_traces = make_traces(info.dates, info.values, 'bar', date_formatter);

    const dates = data.end_times.map(function (timestamp) {
        return new Date(timestamp * 1000);
    });
    values = {everyone: partial_sums(data.everyone.read),
              me: partial_sums(data.user.read)};
    date_formatter = function (date) {
        return format_date(date, true);
    };
    const cumulative_traces = make_traces(dates, values, 'scatter', date_formatter);

    // Functions to draw and interact with the plot

    // We need to redraw plot entirely if switching from (the cumulative) line
    // graph to any bar graph, since otherwise the rangeselector shows both (plotly bug)
    let clicked_cumulative = false;

    function draw_or_update_plot(rangeselector, traces, last_value_is_partial, initial_draw) {
        $('#read_daily_button, #read_weekly_button, #read_cumulative_button').removeClass("selected");
        $('#id_messages_read_over_time > div').removeClass("spinner");
        if (initial_draw) {
            traces.everyone.visible = true;
            traces.me.visible = 'legendonly';
        } else {
            const plotDiv = document.getElementById('id_messages_read_over_time');
            traces.me.visible = plotDiv.data[0].visible;
            traces.everyone.visible = plotDiv.data[1].visible;
        }
        layout.xaxis.rangeselector = rangeselector;
        if (clicked_cumulative || initial_draw) {
            Plotly.newPlot('id_messages_read_over_time',
                           [traces.me, traces.everyone], layout, {displayModeBar: false});
            add_hover_handler();
        } else {
            Plotly.deleteTraces('id_messages_read_over_time', [0, 1]);
            Plotly.addTraces('id_messages_read_over_time', [traces.me, traces.everyone]);
            Plotly.relayout('id_messages_read_over_time', layout);
        }
        $('#id_messages_read_over_time').attr('last_value_is_partial', last_value_is_partial);
    }

    // Click handlers for aggregation buttons
    $('#read_daily_button').click(function () {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $('#read_weekly_button').click(function () {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, false);
        $(this).addClass("selected");
        clicked_cumulative = false;
    });

    $('#read_cumulative_button').click(function () {
        clicked_cumulative = false;
        draw_or_update_plot(daily_rangeselector, cumulative_traces, false, false);
        $(this).addClass("selected");
        clicked_cumulative = true;
    });

    // Initial drawing of plot
    if (weekly_traces.everyone.x.length < 12) {
        draw_or_update_plot(daily_rangeselector, daily_traces, last_day_is_partial, true);
        $('#read_daily_button').addClass("selected");
    } else {
        draw_or_update_plot(weekly_rangeselector, weekly_traces, last_week_is_partial, true);
        $('#read_weekly_button').addClass("selected");
    }
}

function get_chart_data(data, callback) {
    $.get({
        url: '/json/analytics/chart_data' + page_params.data_url_suffix,
        data: data,
        idempotent: true,
        success: function (data) {
            callback(data);
            update_last_full_update(data.end_times);
        },
        error: function (xhr) {
            $('#id_stats_errors').show().text(JSON.parse(xhr.responseText).msg);
        },
    });
}

get_chart_data(
    {chart_name: 'messages_sent_over_time', min_length: '10'},
    populate_messages_sent_over_time
);

get_chart_data(
    {chart_name: 'messages_sent_by_client', min_length: '10'},
    populate_messages_sent_by_client
);

get_chart_data(
    {chart_name: 'messages_sent_by_message_type', min_length: '10'},
    populate_messages_sent_by_message_type
);

get_chart_data(
    {chart_name: 'number_of_humans', min_length: '10'},
    populate_number_of_users
);

get_chart_data(
    {chart_name: 'messages_read_over_time', min_length: '10'},
    populate_messages_read_over_time
);

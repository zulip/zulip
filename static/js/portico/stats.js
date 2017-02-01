function partial_sums(data) {
    var count1 = 0;
    var count2 = 0;
    var humans_cumulative = [];
    var bots_cumulative = [];

    // Assumed that data.humans.length == data.bots.length
    for (var i = 0; i < data.realm.human.length; i+=1) {
        count1 += data.realm.human[i];
        humans_cumulative[i] = count1;
        count2 += data.realm.bot[i];
        bots_cumulative[i] = count2;
    }
    return [humans_cumulative, bots_cumulative];
}

function get_bins(data, daily_or_weekly) {
    var dates = data.end_times.map(function (timestamp) {
            return new Date(timestamp*1000);
    });
    var new_dates = [];
    var new_humans = [];
    var new_bots = [];
    var current;
    var human_count = 0;
    var bot_count = 0;
    var condition;
    for (var i = 0; i < dates.length; i+=1) {
        if (daily_or_weekly === "daily") {
            condition = dates[i].getHours();
        } else if (daily_or_weekly === "weekly") {
            condition = dates[i].getHours() + dates[i].getDay();
        }
        if (condition === 0) {
            if (current !== undefined) {
                new_dates.push(current);
                new_humans.push(human_count);
                new_bots.push(bot_count);
            }
            current = dates[i];
            human_count = data.realm.human[i];
            bot_count = data.realm.bot[i];
        } else {
            human_count += data.realm.human[i];
            bot_count += data.realm.bot[i];
        }
    }
    new_dates.push(current);
    new_humans.push(human_count);
    new_bots.push(bot_count);
    return [new_dates, new_humans, new_bots];
}

function make_trace(x, y, type, name, hoverinfo, text, visible) {
    var trace = {
        x: x,
        y: y,
        type: type,
        name: name,
        hoverinfo: hoverinfo,
        text: text,
        visible: visible,
    };
    return trace;
}

// returns mm/dd/yyyy for now
function format_date(date_object) {
    var month_abbreviations = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var date = date_object;
    var day = date.getDate();
    var month = date.getMonth();
    var hour = date.getHours();
    var hour_12;
    var suffix;
    if (hour === 0) {
        suffix = ' AM';
        hour_12 = 12;
    } else if (hour === 12) {
        suffix = ' PM';
        hour_12 = hour;
    } else if (hour < 12) {
        suffix = ' AM';
        hour_12 = hour;
    } else {
        suffix = 'PM';
        hour_12 = hour-12;
    }
    return month_abbreviations[month] + ' ' + day + ', ' + hour_12 + suffix;
}

function date_ranges_for_hover(trace_x, window_size) {
    var date_ranges = [];
    for (var j = 0; j < trace_x.length-1; j+=1) {
        var beginning = format_date(trace_x[0]);
        var end;
        if (j < window_size) {
            end = format_date(trace_x[j+1]);
            date_ranges[j] = beginning + '-' + end;
        } else {
            beginning = format_date(trace_x[j]);
            end = format_date(trace_x[j+1]);
            date_ranges[j] = beginning + ' - ' + end;
        }
    }
    date_ranges.push(format_date(trace_x[trace_x.length-1]) + ' - ' + "present");
    return date_ranges;
}

function get_layout(rangeselector_x, rangeselector_y, button_1_count, button_1_label,
                    button_1_step, button_2_count, button_2_label, button_2_step) {
    var layout = {
        barmode:'group',
        width: 750,
        height: 500,
        margin: {
            l: 40, r: 0, b: 150, t: 0,
        },
        xaxis: {
            rangeselector: {
                x: rangeselector_x,
                y: rangeselector_y,
                buttons: [
                    {count:button_1_count,
                         label:button_1_label,
                         step:button_1_step,
                         stepmode:'backward'},
                    {count:button_2_count,
                        label:button_2_label,
                        step:button_2_step,
                        stepmode:'backward'},
                    {
                        step:'all',
                        label: 'All time',
                    },
                ],
            },
            rangeslider: {
                bordercolor:'#D8D8D8',
                borderwidth: 1,
            },
            type: 'date',
        },
        yaxis: {
            fixedrange: true,
            rangemode: 'tozero',
        },
        legend: {
            x: 0.75,
            y: 1.12,
            orientation: "h",
        },
    };
    return layout;
}

function hover(id) {
    var myPlot = document.getElementById(id);
    var hoverInfo = document.getElementById('hoverinfo');
    myPlot.on('plotly_hover', function (data) {
        var date_range;
        var infotext = data.points.map(function (d) {
            var text = d.data.text;
            var index = data.points[0].pointNumber;
            if (text === '') {
                date_range = format_date(d.data.x[index]);
            } else {
                date_range = d.data.text[index];
            }
            return (d.data.name + ': ' + d.y);
        });
        hoverInfo.innerHTML = date_range + '<br/>' + infotext.join('<br/>');
    });
}

function populate_messages_sent_to_realm_bar(data) {
    var end_dates = data.end_times.map(function (timestamp) {
            return new Date(timestamp*1000);
    });
    var trace_humans = make_trace(end_dates, data.realm.human, 'bar', "Humans", 'none', '', true);
    var trace_bots = make_trace(end_dates, data.realm.bot, 'bar', "Bots", 'none', '', true);

    var cumulative_sums = partial_sums(data);
    var humans_cumulative = cumulative_sums[0];
    var bots_cumulative = cumulative_sums[1];
    var trace_humans_cumulative = make_trace(end_dates, humans_cumulative, 'scatter', "Humans", 'none', '', true);
    var trace_bots_cumulative = make_trace(end_dates, bots_cumulative, 'scatter', "Bots", 'none', '', true);

    var weekly_bins = get_bins(data, "weekly");
    var dates_weekly = weekly_bins[0];
    var humans_weekly = weekly_bins[1];
    var bots_weekly = weekly_bins[2];
    var date_range_weekly = date_ranges_for_hover(dates_weekly, 1);
    var trace_humans_weekly = make_trace(dates_weekly, humans_weekly, 'bar', "Humans", 'none', date_range_weekly, true);
    var trace_bots_weekly = make_trace(dates_weekly, bots_weekly, 'bar', "Bots", 'none', date_range_weekly, true);

    var daily_bins = get_bins(data, "daily");
    var dates_daily = daily_bins[0];
    var humans_daily = daily_bins[1];
    var bots_daily = daily_bins[2];
    var date_range_daily = date_ranges_for_hover(dates_daily, 1);
    var trace_humans_daily = make_trace(dates_daily, humans_daily, 'bar', "Humans", 'none', date_range_daily, true);
    var trace_bots_daily = make_trace(dates_daily, bots_daily, 'bar', "Bots", 'none', date_range_daily, true);


    var layout = get_layout(0.68, -0.62, 10, 'Last 10 Days', 'day', 30, 'Last 30 Days', 'day');

    Plotly.newPlot('id_messages_sent_to_realm_bar',
                   [trace_humans_daily, trace_bots_daily], layout, {displayModeBar: false});

    hover('id_messages_sent_to_realm_bar');

    var clicked_cumulative = false;

    $('#cumulative_button').click(function () {
        clicked_cumulative = true;
        $(this).css('background', '#D8D8D8');
        $('#daily_button').css('background', '#F0F0F0');
        $('#weekly_button').css('background', '#F0F0F0');
        $('#hourly_button').css('background', '#F0F0F0');
        Plotly.deleteTraces('id_messages_sent_to_realm_bar', [0,1]);
        Plotly.addTraces('id_messages_sent_to_realm_bar', [trace_humans_cumulative, trace_bots_cumulative]);
        var layout1 = get_layout(0.68, -0.62, 10, 'Last 10 Days', 'day', 30, 'Last 30 Days', 'day');
        Plotly.relayout('id_messages_sent_to_realm_bar', layout1);
    });

    $('#daily_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#cumulative_button').css('background', '#F0F0F0');
        $('#weekly_button').css('background', '#F0F0F0');
        $('#hourly_button').css('background', '#F0F0F0');
        var layout1 = get_layout(0.68, -0.62, 10, 'Last 10 Days', 'day', 30, 'Last 30 Days', 'day');
        if (clicked_cumulative) {
            Plotly.newPlot('id_messages_sent_to_realm_bar',
                   [trace_humans_daily, trace_bots_daily], layout1, {displayModeBar: false});
            hover('id_messages_sent_to_realm_bar');
        } else {
            Plotly.deleteTraces('id_messages_sent_to_realm_bar', [0,1]);
            Plotly.addTraces('id_messages_sent_to_realm_bar', [trace_humans_daily, trace_bots_daily]);
            Plotly.relayout('id_messages_sent_to_realm_bar', layout1);
        }
        clicked_cumulative = false;
    });

    $('#weekly_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#daily_button').css('background', '#F0F0F0');
        $('#cumulative_button').css('background', '#F0F0F0');
        $('#hourly_button').css('background', '#F0F0F0');
        var layout1 = get_layout(0.656, -0.62, 2, 'Last 2 Months', 'month', 6, 'Last 6 Months', 'month');

        if (clicked_cumulative) {
            Plotly.newPlot('id_messages_sent_to_realm_bar',
                   [trace_humans_weekly, trace_bots_weekly], layout1, {displayModeBar: false});
            hover('id_messages_sent_to_realm_bar');
        } else {
            Plotly.deleteTraces('id_messages_sent_to_realm_bar', [0,1]);
            Plotly.addTraces('id_messages_sent_to_realm_bar', [trace_humans_weekly, trace_bots_weekly]);
            Plotly.relayout('id_messages_sent_to_realm_bar', layout1);
        }
        clicked_cumulative = false;
    });

    $('#hourly_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#daily_button').css('background', '#F0F0F0');
        $('#weekly_button').css('background', '#F0F0F0');
        $('#cumulative_button').css('background', '#F0F0F0');
        var layout1 = get_layout (0.66, -0.62, 24, 'Last 24 Hours', 'hour', 72, 'Last 72 Hours', 'hour');
        if (clicked_cumulative) {
            Plotly.newPlot('id_messages_sent_to_realm_bar',
                   [trace_humans, trace_bots], layout1, {displayModeBar: false});
            hover('id_messages_sent_to_realm_bar');
        } else {
            Plotly.deleteTraces('id_messages_sent_to_realm_bar', [0,1]);
            Plotly.addTraces('id_messages_sent_to_realm_bar', [trace_humans, trace_bots]);
            Plotly.relayout('id_messages_sent_to_realm_bar', layout1);
        }
        clicked_cumulative = false;
    });
}

$.get({
    url: '/json/analytics/chart_data',
    data: {chart_name: 'messages_sent_by_humans_and_bots', min_length: '10'},
    idempotent: true,
    success: function (data) {
        populate_messages_sent_to_realm_bar(data);
    },
    error: function (xhr) {
        $('#id_stats_errors').text($.parseJSON(xhr.responseText).msg);
    },
});

function populate_number_of_users(data) {
    var end_dates = data.end_times.map(function (timestamp) {
            return new Date(timestamp*1000);
    });
    var trace_humans = make_trace(end_dates, data.realm.human, 'bar', "Active users", 'y', true, '');

    var layout = {
        width: 750,
        height: 370,
        margin: {
            l: 40, r: 0, b: 0, t: 20,
        },
        xaxis: {
            rangeselector: {
                x: 0.75,
                y:-0.2,
                buttons: [
                    {count:30,
                        label:'Last 30 Days',
                        step:'day',
                        stepmode:'backward'},
                    {
                        step:'all',
                        label: 'All time',
                    },
                ],
            },
        },
        yaxis: {
            fixedrange: true,
            rangemode: 'tozero',
        },
    };
    Plotly.newPlot('id_number_of_users',
                   [trace_humans], layout, {displayModeBar: false});
}

$.get({
    url: '/json/analytics/chart_data',
    data: {chart_name: 'number_of_humans', min_length: '10'},
    idempotent: true,
    success: function (data) {
        populate_number_of_users(data);
    },
    error: function (xhr) {
        $('#id_stats_errors').text($.parseJSON(xhr.responseText).msg);
    },
});

function make_pie_trace(data, values, labels, text) {
    var trace = [{
        values: values,
        labels: labels,
        type: 'pie',
        direction: 'clockwise',
        rotation: -180,
        sort: true,
        // textposition: textposition,
        textinfo: "text",
        text: text,
        hoverinfo: "label+text",
    }];
    return trace;
}

function round_percentages(values) {
    var total = values.reduce(function (a, b) { return a + b; }, 0);
    var percents = values.map(function (x) {
        var unrounded = x/total*100;
        var rounded;
        if (unrounded > 99.4) {
            rounded = unrounded.toPrecision(3);
        } else {
            rounded = unrounded.toPrecision(2);
        }
        return rounded + '%';
    });
    return [total, percents];
}

function get_labels_and_data(names, data_subgroup, time_frame_integer) {
    var labels = [];
    var values = [];
    for (var key in data_subgroup) {
        if (data_subgroup.hasOwnProperty(key)) {
            var sum = 0;
            for (var i = time_frame_integer - 1; i >= 0; i-=1) {
                sum += data_subgroup[key][i];
            }
            if (sum > 0) {
                values.push(sum);
                labels.push(names[key]);
            }
        }
    }
    return [labels, values];
}

function populate_messages_sent_by_client(data) {
    var names = {
        electron_: "Electron",
        barnowl_: "BarnOwl",
        website_: "Website",
        API_: "API",
        android_: "Android",
        iOS_: "iOS",
        react_native_: "React Native",
    };
    var realm_cumulative = get_labels_and_data(names, data.realm, data.end_times.length);
    var realm_labels_cumulative = realm_cumulative[0];
    var realm_values_cumulative = realm_cumulative[1];
    var realm_percentages_cumulative = round_percentages(realm_values_cumulative);
    var realm_total_cumulative = realm_percentages_cumulative[0];
    var realm_text_cumulative = realm_percentages_cumulative[1];

    var realm_values_ten_days = get_labels_and_data(names, data.realm, 10)[1];
    var realm_percentages_ten_days = round_percentages(realm_values_ten_days);
    var realm_total_ten_days = realm_percentages_ten_days[0];
    var realm_text_ten_days = realm_percentages_ten_days[1];

    var realm_values_thirty_days = get_labels_and_data(names, data.realm, 30)[1];
    var realm_percentages_thirty_days = round_percentages(realm_values_thirty_days);
    var realm_total_thirty_days = realm_percentages_thirty_days[0];
    var realm_text_thirty_days = realm_percentages_thirty_days[1];

    var user_values_cumulative = get_labels_and_data(names, data.user, data.end_times.length)[1];
    var user_percentages_cumulative = round_percentages(user_values_cumulative);
    var user_total_cumulative = user_percentages_cumulative[0];
    var user_text_cumulative = user_percentages_cumulative[1];

    var user_values_ten_days = get_labels_and_data(names, data.user, 10)[1];
    var user_percentages_ten_days = round_percentages(user_values_ten_days);
    var user_total_ten_days = user_percentages_ten_days[0];
    var user_text_ten_days = user_percentages_ten_days[1];

    var user_values_thirty_days = get_labels_and_data(names, data.user, 30)[1];
    var user_percentages_thirty_days = round_percentages(user_values_thirty_days);
    var user_total_thirty_days = user_percentages_thirty_days[0];
    var user_text_thirty_days = user_percentages_thirty_days[1];

    var trace = make_pie_trace(data, realm_values_cumulative,
                               realm_labels_cumulative, realm_text_cumulative);
    var layout = {
        margin: {
            l: 0, r: 0, b: 50, t: 30,
        },
        width: 375,
        height: 400,
    };
    Plotly.newPlot('id_messages_sent_by_client', trace, layout, {displayModeBar: false});

    var total = document.getElementById('pie1_total');
    total.innerHTML = "Total messages: " +
        realm_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

    var time_range = 'cumulative';
    var type_data = 'realm';

    $('#messages_by_client_realm_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_client_user_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_client');
        type_data = 'realm';
        if (time_range === 'cumulative') {
            plotDiv.data[0].values = realm_values_cumulative;
            plotDiv.data[0].text = realm_text_cumulative;
            total.innerHTML = "Total messages: " +
                realm_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else if (time_range === 'ten') {
            plotDiv.data[0].values = realm_values_ten_days;
            plotDiv.data[0].text = realm_text_ten_days;
            total.innerHTML = "Total messages: " +
                realm_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = realm_values_thirty_days;
            plotDiv.data[0].text = realm_text_thirty_days;
            total.innerHTML = "Total messages: " +
                realm_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_client');

    });
    $('#messages_by_client_user_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_client_realm_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_client');
        type_data = 'user';
        if (time_range === 'cumulative') {
            plotDiv.data[0].values = user_values_cumulative;
            plotDiv.data[0].text = user_text_cumulative;
            total.innerHTML = "Total messages: " +
                user_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else if (time_range === 'ten') {
            plotDiv.data[0].values = user_values_ten_days;
            plotDiv.data[0].text = user_text_ten_days;
            total.innerHTML = "Total messages: " +
                user_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_thirty_days;
            plotDiv.data[0].text = user_text_thirty_days;
            total.innerHTML = "Total messages: " +
                user_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_client');

    });

    $('#messages_by_client_ten_days_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_client_thirty_days_button').css('background', '#F0F0F0');
        $('#messages_by_client_cumulative_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_client');
        time_range = 'ten';
        if (type_data === 'realm') {
            plotDiv.data[0].values = realm_values_ten_days;
            plotDiv.data[0].text = realm_text_ten_days;
            total.innerHTML = "Total messages: " +
                realm_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_ten_days;
            plotDiv.data[0].text = user_text_ten_days;
            total.innerHTML = "Total messages: " +
                user_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_client');
    });

    $('#messages_by_client_thirty_days_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_client_ten_days_button').css('background', '#F0F0F0');
        $('#messages_by_client_cumulative_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_client');
        time_range = 'thirty';
        if (type_data === 'realm') {
            plotDiv.data[0].values = realm_values_thirty_days;
            plotDiv.data[0].text = realm_text_thirty_days;
            total.innerHTML = "Total messages: " +
                realm_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_thirty_days;
            plotDiv.data[0].text = user_text_thirty_days;
            total.innerHTML = "Total messages: " +
                user_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_client');
    });

    $('#messages_by_client_cumulative_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_client_thirty_days_button').css('background', '#F0F0F0');
        $('#messages_by_client_ten_days_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_client');
        time_range = 'cumulative';
        if (type_data === 'realm') {
            plotDiv.data[0].values = realm_values_cumulative;
            plotDiv.data[0].text = realm_text_cumulative;
            total.innerHTML = "Total messages: " +
                realm_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_cumulative;
            plotDiv.data[0].text = user_text_cumulative;
            total.innerHTML = "Total messages: " +
                user_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_client');
    });
}

$.get({
    url: '/json/analytics/chart_data',
    data: {chart_name: 'messages_sent_by_client', min_length: '10'},
    idempotent: true,
    success: function (data) {
        populate_messages_sent_by_client(data);
    },
    error: function (xhr) {
        $('#id_stats_errors').text($.parseJSON(xhr.responseText).msg);
    },
});

function populate_messages_sent_by_message_type(data) {
    var names = {
        public_stream: "Public Stream",
        private_stream: "Private Stream",
        private_message: "Private Message",
    };
    var realm_cumulative = get_labels_and_data(names, data.realm, data.end_times.length);
    var realm_labels_cumulative = realm_cumulative[0];
    var realm_values_cumulative = realm_cumulative[1];
    var realm_percentages_cumulative = round_percentages(realm_values_cumulative);
    var realm_total_cumulative = realm_percentages_cumulative[0];
    var realm_text_cumulative = realm_percentages_cumulative[1];

    var realm_values_ten_days = get_labels_and_data(names, data.realm, 10)[1];
    var realm_percentages_ten_days = round_percentages(realm_values_ten_days);
    var realm_total_ten_days = realm_percentages_ten_days[0];
    var realm_text_ten_days = realm_percentages_ten_days[1];

    var realm_values_thirty_days = get_labels_and_data(names, data.realm, 30)[1];
    var realm_percentages_thirty_days = round_percentages(realm_values_thirty_days);
    var realm_total_thirty_days = realm_percentages_thirty_days[0];
    var realm_text_thirty_days = realm_percentages_thirty_days[1];

    var user_values_cumulative = get_labels_and_data(names, data.user, data.end_times.length)[1];
    var user_percentages_cumulative = round_percentages(user_values_cumulative);
    var user_total_cumulative = user_percentages_cumulative[0];
    var user_text_cumulative = user_percentages_cumulative[1];

    var user_values_ten_days = get_labels_and_data(names, data.user, 10)[1];
    var user_percentages_ten_days = round_percentages(user_values_ten_days);
    var user_total_ten_days = user_percentages_ten_days[0];
    var user_text_ten_days = user_percentages_ten_days[1];

    var user_values_thirty_days = get_labels_and_data(names, data.user, 30)[1];
    var user_percentages_thirty_days = round_percentages(user_values_thirty_days);
    var user_total_thirty_days = user_percentages_thirty_days[0];
    var user_text_thirty_days = user_percentages_thirty_days[1];

    var trace = make_pie_trace(data, realm_values_cumulative,
                               realm_labels_cumulative, realm_text_cumulative);

    var total = document.getElementById('pie2_total');
    total.innerHTML = "Total messages: " +
        realm_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

    var layout = {
        margin: {
            l: 0, r: 0, b: 50, t: 30,
        },
        width: 375,
        height: 400,
    };
    Plotly.newPlot('id_messages_sent_by_message_type', trace, layout, {displayModeBar: false});

    var time_range = 'cumulative';
    var type_data = 'realm';

    $('#messages_by_type_realm_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_type_user_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_message_type');
        type_data = 'realm';
        if (time_range === 'cumulative') {
            plotDiv.data[0].values = realm_values_cumulative;
            plotDiv.data[0].text = realm_text_cumulative;
            total.innerHTML = "Total messages: " +
                realm_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else if (time_range === 'ten') {
            plotDiv.data[0].values = realm_values_ten_days;
            plotDiv.data[0].text = realm_text_ten_days;
            total.innerHTML = "Total messages: " +
                realm_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = realm_values_thirty_days;
            plotDiv.data[0].text = realm_text_thirty_days;
            total.innerHTML = "Total messages: " +
                realm_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_message_type');

    });
    $('#messages_by_type_user_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_type_realm_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_message_type');
        type_data = 'user';
        if (time_range === 'cumulative') {
            plotDiv.data[0].values = user_values_cumulative;
            plotDiv.data[0].text = user_text_cumulative;
            total.innerHTML = "Total messages: " +
                user_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else if (time_range === 'ten') {
            plotDiv.data[0].values = user_values_ten_days;
            plotDiv.data[0].text = user_text_ten_days;
            total.innerHTML = "Total messages: " +
                user_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_thirty_days;
            plotDiv.data[0].text = user_text_thirty_days;
            total.innerHTML = "Total messages: " +
                user_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_message_type');

    });

    $('#messages_by_type_ten_days_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_type_thirty_days_button').css('background', '#F0F0F0');
        $('#messages_by_type_cumulative_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_message_type');
        time_range = 'ten';
        if (type_data === 'realm') {
            plotDiv.data[0].values = realm_values_ten_days;
            plotDiv.data[0].text = realm_text_ten_days;
            total.innerHTML = "Total messages: " +
                realm_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_ten_days;
            plotDiv.data[0].text = user_text_ten_days;
            total.innerHTML = "Total messages: " +
                user_total_ten_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_message_type');
    });

    $('#messages_by_type_thirty_days_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_type_ten_days_button').css('background', '#F0F0F0');
        $('#messages_by_type_cumulative_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_message_type');
        time_range = 'thirty';
        if (type_data === 'realm') {
            plotDiv.data[0].values = realm_values_thirty_days;
            plotDiv.data[0].text = realm_text_thirty_days;
            total.innerHTML = "Total messages: " +
                realm_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_thirty_days;
            plotDiv.data[0].text = user_text_thirty_days;
            total.innerHTML = "Total messages: " +
                user_total_thirty_days.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_message_type');
    });

    $('#messages_by_type_cumulative_button').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#messages_by_type_thirty_days_button').css('background', '#F0F0F0');
        $('#messages_by_type_ten_days_button').css('background', '#F0F0F0');
        var plotDiv = document.getElementById('id_messages_sent_by_message_type');
        time_range = 'cumulative';
        if (type_data === 'realm') {
            plotDiv.data[0].values = realm_values_cumulative;
            plotDiv.data[0].text = realm_text_cumulative;
            total.innerHTML = "Total messages: " +
                realm_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        } else {
            plotDiv.data[0].values = user_values_cumulative;
            plotDiv.data[0].text = user_text_cumulative;
            total.innerHTML = "Total messages: " +
                user_total_cumulative.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        Plotly.redraw('id_messages_sent_by_message_type');
    });
}

$.get({
    url: '/json/analytics/chart_data',
    data: {chart_name: 'messages_sent_by_message_type', min_length: '10'},
    idempotent: true,
    success: function (data) {
        populate_messages_sent_by_message_type(data);
    },
    error: function (xhr) {
        $('#id_stats_errors').text($.parseJSON(xhr.responseText).msg);
    },
});

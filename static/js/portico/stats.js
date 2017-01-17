function partial_sums(data) {
    var count1 = 0;
    var count2 = 0;
    var humans_cumulative = [];
    var bots_cumulative = [];

    // Assumed that data.humans.length == data.bots.length
    for (var i = 0; i < data.humans.length; i+=1) {
        count1 += data.humans[i];
        humans_cumulative[i] = count1;
        count2 += data.bots[i];
        bots_cumulative[i] = count2;
    }
    return [humans_cumulative, bots_cumulative];
}

function window_sums(cumulative_sums, window_size) {
    var humans_cumulative = cumulative_sums[0];
    var bots_cumulative = cumulative_sums[1];
    var humans_windowsums = [];
    var bots_windowsums = [];

    for (var j = 0; j < humans_cumulative.length; j+=1) {
        if (j < window_size) {
            humans_windowsums[j] = humans_cumulative[j];
            bots_windowsums[j] = bots_cumulative[j];
        } else {
            humans_windowsums[j] = humans_cumulative[j] - humans_cumulative[j-window_size];
            bots_windowsums[j] = bots_cumulative[j] - bots_cumulative[j-window_size];
        }
    }
    return [humans_windowsums, bots_windowsums];
}

function make_bar_trace(data, y, name, hoverinfo, visible, text) {
    var trace = {
        x: data.end_times.map(function (timestamp) {
            return new Date(timestamp*1000);
        }),
        y: y,
        type: 'bar',
        name: name,
        hoverinfo: hoverinfo,
        visible: visible,
        text: text,
    };
    return trace;
}

// returns mm/dd/yyyy for now
function format_date(date_object) {
    var month_abbreviations = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    var date = date_object;
    var day = date.getDate();
    var month = date.getMonth();
    return month_abbreviations[month] + ' ' + day;
}

function date_ranges_for_hover(trace_x, window_size) {
    var date_ranges = [];
    for (var j = 0; j < trace_x.length; j+=1) {
        var beginning = format_date(trace_x[0]);
        var today;
        if (j < window_size) {
            today = format_date(trace_x[j]);
            date_ranges[j] = beginning + '-' + today;
        } else {
            beginning = format_date(trace_x[j-window_size]);
            today = format_date(trace_x[j]);
            date_ranges[j] = beginning + ' - ' + today;
        }
    }
    return date_ranges;
}

function populate_messages_sent_to_realm_bar(data) {

    var trace_humans = make_bar_trace(data, data.humans, "Messages from humans", 'x+y', true, '');
    var trace_bots = make_bar_trace(data, data.bots, "Messages from bots", 'x+y', true, '');

    var cumulative_sums = partial_sums(data);
    var humans_cumulative = cumulative_sums[0];
    var bots_cumulative = cumulative_sums[1];
    var trace_humans_cumulative = make_bar_trace(data, humans_cumulative, "Messages from humans", 'x+y', false, '');
    var trace_bots_cumulative = make_bar_trace(data, bots_cumulative, "Messages from bots", 'x+y', false, '');

    var weekly_sums = window_sums(cumulative_sums, 7);
    var humans_weekly = weekly_sums[0];
    var bots_weekly = weekly_sums[1];
    var date_range_weekly = date_ranges_for_hover(trace_humans.x, 7);
    var trace_humans_weekly = make_bar_trace(data, humans_weekly, "Messages from humans", 'y+text', false, date_range_weekly);
    var trace_bots_weekly = make_bar_trace(data, bots_weekly, "Messages from bots", 'y+text', false, date_range_weekly);

    var monthly_sums = window_sums(cumulative_sums, 28);
    var humans_4weekly = monthly_sums[0];
    var bots_4weekly = monthly_sums[1];
    var date_range_4weekly = date_ranges_for_hover(trace_humans.x, 28);
    var trace_humans_4weekly = make_bar_trace(data, humans_4weekly, "Messages from humans", 'y+text', false, date_range_4weekly);
    var trace_bots_4weekly = make_bar_trace(data, bots_4weekly, "Messages from bots", 'y+text', false, date_range_4weekly);


    var layout = {
        barmode:'group',
        width: 900,
        margin: {
            l: 50, r: 50, b: 100, t: 5,
        },
        xaxis: {
            rangeselector: {
                x: 0.65,
                y:-0.5,
                buttons: [
                    {count:10,
                         label:'Last 10 Days',
                         step:'day',
                         stepmode:'backward'},
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
            rangeslider:{},
            type: 'date',
        },
        yaxis: {
            fixedrange: true,
            rangemode: 'tozero',
        },
    };
    Plotly.newPlot('id_messages_sent_to_realm_bar',
                   [trace_humans, trace_bots, trace_humans_cumulative,trace_bots_cumulative,
                   trace_humans_weekly, trace_bots_weekly, trace_humans_4weekly,
                   trace_bots_4weekly], layout, {displayModeBar: false});

    $('#cumulative').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#daily').css('background', '#F0F0F0');
        $('#weekly').css('background', '#F0F0F0');
        $('#monthly').css('background', '#F0F0F0');
        var update1 = {visible:false};
        var update2 = {visible:true};
        Plotly.restyle('id_messages_sent_to_realm_bar', update1, [0,1,4,5,6,7]);
        Plotly.restyle('id_messages_sent_to_realm_bar', update2, [2,3]);
    });

    $('#daily').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#cumulative').css('background', '#F0F0F0');
        $('#weekly').css('background', '#F0F0F0');
        $('#monthly').css('background', '#F0F0F0');
        var update1 = {visible:false};
        var update2 = {visible:true};
        Plotly.restyle('id_messages_sent_to_realm_bar', update2, [0,1]);
        Plotly.restyle('id_messages_sent_to_realm_bar', update1, [2,3,4,5,6,7]);
    });

    $('#weekly').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#daily').css('background', '#F0F0F0');
        $('#cumulative').css('background', '#F0F0F0');
        $('#monthly').css('background', '#F0F0F0');
        var update1 = {visible:false};
        var update2 = {visible:true};
        Plotly.restyle('id_messages_sent_to_realm_bar', update2, [4,5]);
        Plotly.restyle('id_messages_sent_to_realm_bar', update1, [0,1,2,3,6,7]);
    });

    $('#monthly').click(function () {
        $(this).css('background', '#D8D8D8');
        $('#daily').css('background', '#F0F0F0');
        $('#weekly').css('background', '#F0F0F0');
        $('#cumulative').css('background', '#F0F0F0');
        var update1 = {visible:false};
        var update2 = {visible:true};
        Plotly.restyle('id_messages_sent_to_realm_bar', update2, [6,7]);
        Plotly.restyle('id_messages_sent_to_realm_bar', update1, [0,1,2,3,4,5]);
    });

    var myPlot = document.getElementById('id_messages_sent_to_realm_bar');
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
        hoverInfo.innerHTML = 'Date range: '+ date_range + '<br/>' + infotext.join('<br/>');
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
    var trace_humans = make_bar_trace(data, data.humans, "Active users", 'x+y', true, '');

    var layout = {
        title: 'Number of Users',
        width: 750,
        height: 350,
        margin: {
            l: 50, r: 50, b: 30, t: 60,
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

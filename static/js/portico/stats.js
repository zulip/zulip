function populate_messages_sent_to_realm(data) {
    var trace_humans = {
        x: data.end_times.map(function (timestamp) {
            return new Date(timestamp*1000);
        }),
        y: data.humans,
        mode: 'lines',
        name: 'Messages from humans',
        hoverinfo: 'y'
    };

    var trace_bots = {
        x: data.end_times.map(function (timestamp) {
            return new Date(timestamp*1000);
        }),
        y: data.bots,
        mode: 'lines',
        name: 'Messages from bots',
        hoverinfo: 'y'
    };

    var layout = {
        title: 'Messages sent by humans and bots',
        xaxis: {
            type: 'date',
        },
        yaxis: {
            fixedrange: true,
            rangemode: 'tozero',
        }
    };

    Plotly.newPlot('id_messages_sent_to_realm', [trace_humans, trace_bots], layout, {displayModeBar: false});
}

$.get({
    url: '/json/analytics/chart_data',
    data: {chart_name: 'messages_sent_to_realm', min_length: '10'},
    idempotent: true,
    success: function (data) {
        populate_messages_sent_to_realm(data);
    },
    error: function (xhr) {
        $('#id_stats_errors').text($.parseJSON(xhr.responseText).msg);
    }
});

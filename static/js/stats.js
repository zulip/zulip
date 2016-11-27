// Get messages sent data
$.get("/json/get-messages-chart-data", function (response) {
    populate_chart(response);
});
function populate_chart(data) {
    var interval_select = document.getElementById("interval");
    var selectorOptions = {
        buttons: [{
            step: 'day',
            stepmode: 'backward',
            count: 30,
            label: 'Last 30 Days'
        }, {
            step: 'week',
            stepmode: 'backward',
            count: 1,
            label: 'Last Week'
        }, {
            step: 'all',
            label: 'All Time'
        }],
    };

    var trace1 = {
        x: data.dates.map(function (o) {
            return new Date(o * 1000);
        }),
        y: data.rows.map(function (o) {
            return o[1];
        }),
        mode: 'lines',
        name: 'Messages from humans',
        hoverinfo: 'y'
    };

    var trace2 = {
        x: data.dates.map(function (o) {
            return new Date(o * 1000);
        }),
        y: data.rows.map(function (o) {
            return o[2];
        }),
        mode: 'lines',
        name: 'Messages from bots',
        hoverinfo: 'y'

    };

    window.chart_data = [trace1, trace2];

    var layout = {
        title: data.title,
        xaxis: {
            rangeselector: selectorOptions
        },
        yaxis: {
            fixedrange: true,
            rangemode: 'nonnegative',

        }
    };

    var chart_interval = {
        daily: function (chart_data) {
            return chart_data;
        },
        weekly: function (chart_data) {
            return chart_data.map(function (chart) {
                var trailing_value = 0;
                // weekly dates
                return {
                    x: chart.x.filter(function (o, i) {
                        return (i - 1) % 7 === 0;
                    }),
                    y: chart.y.map(function (o, i) {
                        if ((i - 1) % 7 === 0) {
                            var t = trailing_value + o;
                            trailing_value = 0;
                            return t;
                        } else {
                            trailing_value += o;
                            return null;
                        }
                    }).filter(function (o) {
                        return o !== null;
                    }),
                    mode: chart.mode,
                    name: chart.name,
                    hoverinfo: chart.hoverinfo
                };
            });
        },
        monthly: function (chart_data) {
            return chart_data.map(function (chart) {
                var trailing_value = 0;
                // monthly dates
                return {
                    x: chart.x.filter(function (o, i) {
                        return (i - 1) % 30 === 0;
                    }),
                    y: chart.y.map(function (o, i) {
                        if ((i - 1) % 30 === 0) {
                            var t = trailing_value + o;
                            trailing_value = 0;
                            return t;
                        } else {
                            trailing_value += o;
                            return null;
                        }
                    }).filter(function (o) {
                        return o !== null;
                    }),
                    mode: chart.mode,
                    name: chart.name,
                    hoverinfo: chart.hoverinfo
                };
            });
        }
    };
    var myPlot = document.querySelector("#plotDiv");

    Plotly.newPlot(myPlot, chart_interval.daily(chart_data), layout, {displayModeBar: false});

    interval.addEventListener("change", function () {
        var chart_values = this.value;
        console.log(chart_values, "VALUES")
        Plotly.newPlot(myPlot, chart_interval[chart_values](chart_data), layout, {displayModeBar: false});

    });

    if (data.dates.length < 7) {
        document.querySelectorAll('select option')[1].disabled = true;
    }
    if (data.dates.length < 30) {
        document.querySelectorAll('select option')[2].disabled = true;
    }
}
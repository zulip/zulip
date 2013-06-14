var metrics = (function () {

var exports = {};

function enable_metrics() {
    return page_params.domain === "humbughq.com";
}

if (! enable_metrics()) {
    mixpanel.disable();
}

mixpanel.register({user: page_params.email, realm: page_params.domain});

function include_in_sample() {
    // Send a random sample of events that we generate
    return Math.random() < 0.1;
}

$(function () {
    $(document).on('compose_started.zephyr', function (event) {
        if (! include_in_sample()) {
            return;
        }

        mixpanel.track('compose started', {type: event.message_type,
                                           trigger: event.trigger},
                       function (arg) {
                           if (arg !== undefined && arg.status !== 1) {
                               blueslip.warn(arg);
                           }
                       });
    });
    $(document).on('narrow_activated.zephyr', function (event) {
        if (! include_in_sample()) {
            return;
        }

        var operators = event.filter.operators();
        var stream_operands = event.filter.operands('stream');
        var subject_operands = event.filter.operands('subject');
        var reported_operators;
        if (operators.length === 1) {
            reported_operators = operators[0][0];
        } else if (operators.length === 2
                   && stream_operands.length !== 0 && subject_operands.length !== 0) {
            reported_operators = 'stream and subject';
        } else {
            reported_operators = 'multiple';
        }

        mixpanel.track('narrow activated', {operators: reported_operators,
                                            trigger: event.trigger},
                       function (arg) {
                           if (arg !== undefined && arg.status !== 1) {
                               blueslip.warn(arg);
                           }
                       });
    });
});

return exports;
}());

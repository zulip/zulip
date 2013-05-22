var metrics = (function () {

var exports = {people: {}};

function enable_metrics() {
    return page_params.domain === "humbughq.com";
}

var methods = ["disable", "track", "track_pageview", "track_links", "track_forms",
               "register", "register_once", "alias", "unregister", "identify",
               "name_tag", "set_config"];
var people_methods = ["set", "set_once", "increment", "append", "track_charge",
                      "clear_charges", "delete_user"];

function wrap_method(name, source_container, target_container_func) {
    source_container[name] = function metrics_wrapper () {
        if (enable_metrics()) {
            // We must reference mixpanel indirectly here because
            // mixpanel loads asynchronously with stub methods and
            // replaces its methods when it fully loads
            var target_container = target_container_func();
            return target_container[name].apply(target_container, arguments);
        }
    };
}

$.each(methods, function (idx, method) {
    wrap_method(method, exports, function () { return mixpanel; });
});

$.each(people_methods, function (idx, method) {
    wrap_method(method, exports.people, function () { return mixpanel.people; });
});

// This should probably move elsewhere
$(function () {
    $(document).on('compose_started.zephyr', function (event) {
        metrics.track('compose started', {user: page_params.email,
                                          realm: page_params.domain,
                                          type: event.message_type,
                                          trigger: event.trigger},
                      function (arg) {
                          if (arg !== undefined && arg.status !== 1) {
                              blueslip.warn(arg);
                          }
                      });
    });
    $(document).on('narrow_activated.zephyr', function (event) {
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

        metrics.track('narrow activated', {user: page_params.email,
                                           realm: page_params.domain,
                                           operators: reported_operators,
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
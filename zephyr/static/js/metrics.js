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

function wrap_method(name, source_container, target_container) {
    source_container[name] = function metrics_wrapper () {
        if (enable_metrics()) {
            return target_container[name].apply(target_container, arguments);
        }
    };
}

$.each(methods, function (idx, method) {
    wrap_method(method, exports, mixpanel);
});

$.each(people_methods, function (idx, method) {
    wrap_method(method, exports.people, mixpanel.people);
});
return exports;
}());
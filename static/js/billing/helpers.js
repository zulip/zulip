exports.create_ajax_request = function (url, form_name, stripe_token = null, numeric_inputs = []) {
    const form = $("#" + form_name + "-form");
    const form_loading_indicator = "#" + form_name + "_loading_indicator";
    const form_input_section = "#" + form_name + "-input-section";
    const form_success = "#" + form_name + "-success";
    const form_error = "#" + form_name + "-error";
    const form_loading = "#" + form_name + "-loading";

    const zulip_limited_section =  "#zulip-limited-section";
    const free_trial_alert_message =  "#free-trial-alert-message";

    loading.make_indicator($(form_loading_indicator),
                           {text: 'Processing ...', abs_positioned: true});
    $(form_input_section).hide();
    $(form_error).hide();
    $(form_loading).show();
    $(zulip_limited_section).hide();
    $(free_trial_alert_message).hide();

    const data = {};
    if (stripe_token) {
        data.stripe_token = JSON.stringify(stripe_token.id);
    }

    form.serializeArray().forEach(function (item) {
        if (numeric_inputs.includes(item.name)) {
            data[item.name] = item.value;
        } else {
            data[item.name] = JSON.stringify(item.value);
        }
    });

    $.post({
        url: url,
        data: data,
        success: function () {
            $(form_loading).hide();
            $(form_error).hide();
            $(form_success).show();
            if (["autopay", "invoice"].includes(form_name)) {
                if ("pushState" in history) {
                    history.pushState("", document.title, location.pathname + location.search);
                } else {
                    location.hash = "";
                }
            }
            location.reload();
        },
        error: function (xhr) {
            $(form_loading).hide();
            $(form_error).show().text(JSON.parse(xhr.responseText).msg);
            $(form_input_section).show();
            $(zulip_limited_section).show();
            $(free_trial_alert_message).show();
        },
    });
};

exports.format_money = function (cents) {
    // allow for small floating point errors
    cents = Math.ceil(cents - 0.001);
    let precision;
    if (cents % 100 === 0) {
        precision = 0;
    } else {
        precision = 2;
    }
    // TODO: Add commas for thousands, millions, etc.
    return (cents / 100).toFixed(precision);
};

exports.update_charged_amount = function (prices, schedule) {
    $("#charged_amount").text(
        exports.format_money(page_params.seat_count * prices[schedule])
    );
};

exports.show_license_section = function (license) {
    $("#license-automatic-section").hide();
    $("#license-manual-section").hide();

    $("#automatic_license_count").prop('disabled', true);
    $("#manual_license_count").prop('disabled', true);

    const section_id = "#license-" + license + "-section";
    $(section_id).show();
    const input_id = "#" + license + "_license_count";
    $(input_id).prop("disabled", false);
};

exports.set_tab = function (page) {
    const hash = location.hash;
    if (hash) {
        $('#' + page + '-tabs.nav a[href="' + hash + '"]').tab('show');
        $('html').scrollTop(0);
    }

    $('#' + page + '-tabs.nav-tabs a').on("click", function () {
        location.hash = this.hash;
    });

    window.onhashchange = function () {
        $('#' + page + '-tabs.nav a[href="' + location.hash + '"]').tab('show');
        $('html').scrollTop(0);
    };
};

exports.is_valid_input = function (elem) {
    return elem[0].checkValidity();
};

window.helpers = exports;

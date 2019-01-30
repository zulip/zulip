var upgrade = (function () {
var exports = {};

exports.initialize = () => {
    helpers.set_tab("upgrade");

    var add_card_handler = StripeCheckout.configure({ // eslint-disable-line no-undef
        key: $("#autopay-form").data("key"),
        image: '/static/images/logo/zulip-icon-128x128.png',
        locale: 'auto',
        token: function (stripe_token) {
            helpers.create_ajax_request("/json/billing/upgrade", "autopay", stripe_token = stripe_token);
        },
    });

    $('#add-card-button').on('click', function (e) {
        var license_management = $('input[type=radio][name=license_management]:checked').val();
        if (helpers.is_valid_input($("#" + license_management + "_license_count")) === false) {
            return;
        }
        add_card_handler.open({
            name: 'Zulip',
            zipCode: true,
            billingAddress: true,
            panelLabel: "Make payment",
            email: $("#autopay-form").data("email"),
            label: "Add card",
            allowRememberMe: false,
            description: "Zulip Cloud Standard",
        });
        e.preventDefault();
    });

    $("#invoice-button").on("click", function (e) {
        if (helpers.is_valid_input($("#invoiced_licenses")) === false) {
            return;
        }
        e.preventDefault();
        helpers.create_ajax_request("/json/billing/upgrade", "invoice");
    });

    var prices = {};
    prices.annual = page_params.annual_price * (1 - page_params.percent_off / 100);
    prices.monthly = page_params.monthly_price * (1 - page_params.percent_off / 100);

    $('input[type=radio][name=license_management]').on("change", function () {
        helpers.show_license_section(this.value);
    });

    $('input[type=radio][name=schedule]').on("change", function () {
        helpers.update_charged_amount(prices, this.value);
    });

    $("#autopay_annual_price").text(helpers.format_money(prices.annual));
    $("#autopay_annual_price_per_month").text(helpers.format_money(prices.annual / 12));
    $("#autopay_monthly_price").text(helpers.format_money(prices.monthly));
    $("#invoice_annual_price").text(helpers.format_money(prices.annual));
    $("#invoice_annual_price_per_month").text(helpers.format_money(prices.annual / 12));

    helpers.show_license_section($('input[type=radio][name=license_management]:checked').val());
    helpers.update_charged_amount(prices, $('input[type=radio][name=schedule]:checked').val());
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = upgrade;
}

window.upgrade = upgrade;

$(function () {
    upgrade.initialize();
});

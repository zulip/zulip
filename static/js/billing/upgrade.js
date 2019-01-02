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
        if ($("#" + license_management + "_license_count")[0].checkValidity() === false) {
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
        if ($("#invoiced_licenses")[0].checkValidity() === false) {
            return;
        }
        e.preventDefault();
        helpers.create_ajax_request("/json/billing/upgrade", "invoice");
    });

    $('input[type=radio][name=license_management]').change(function () {
        helpers.show_license_section($(this).val());
    });

    $('input[type=radio][name=schedule]').change(function () {
        helpers.update_charged_amount($(this).val());
    });

    helpers.set_plan_prices();
    helpers.show_license_section($('input[type=radio][name=license_management]:checked').val());
    helpers.update_charged_amount($('input[type=radio][name=schedule]:checked').val());
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

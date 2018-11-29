$(function () {
    var stripe_key = $("#payment-method").data("key");
    var handler = StripeCheckout.configure({ // eslint-disable-line no-undef
        key: stripe_key,
        image: '/static/images/logo/zulip-icon-128x128.png',
        locale: 'auto',
        token: function (stripe_token) {
            var csrf_token = $("#payment-method").data("csrf");
            loading.make_indicator($('#updating_card_indicator'),
                                   {text: 'Updating card. Please wait ...', abs_positioned: true});
            $("#payment-section").hide();
            $("#loading-section").show();
            $.post({
                url: "/json/billing/sources/change",
                data: {
                    stripe_token: JSON.stringify(stripe_token.id),
                    csrfmiddlewaretoken: csrf_token,
                },
                success: function () {
                    $("#loading-section").hide();
                    $("#card-updated-message").show();
                    location.reload();
                },
                error: function (xhr) {
                    $("#loading-section").hide();
                    $('#error-message-box').show().text(JSON.parse(xhr.responseText).msg);
                },
            });
        },
    });

    $('#update-card-button').on('click', function (e) {
        var email = $("#payment-method").data("email");
        handler.open({
            name: 'Zulip',
            zipCode: true,
            billingAddress: true,
            panelLabel: "Update card",
            email: email,
            label: "Update card",
            allowRememberMe: false,
        });
        e.preventDefault();
    });

    var hash = window.location.hash;
    if (hash) {
        $('#billing-tabs.nav a[href="' + hash + '"]').tab('show');
        $('#upgrade-tabs.nav a[href="' + hash + '"]').tab('show');
        $('html,body').scrollTop(0);
    }

    $('#billing-tabs.nav-tabs a').click(function () {
        $(this).tab('show');
        window.location.hash = this.hash;
        $('html,body').scrollTop(0);
    });

    $('#upgrade-tabs.nav-tabs a').click(function () {
        $(this).tab('show');
        window.location.hash = this.hash;
        $('html,body').scrollTop(0);
    });

    function format_money(cents) {
        // allow for small floating point errors
        cents = Math.ceil(cents - 0.001);
        var precision;
        if (cents % 100 === 0) {
            precision = 0;
        } else {
            precision = 2;
        }
        // TODO: Add commas for thousands, millions, etc.
        return (cents / 100).toFixed(precision);
    }

    if (window.location.pathname === '/upgrade/') {
        var prices = {};
        prices[page_params.nickname_annual] =
            page_params.annual_price
        prices[page_params.nickname_monthly] =
            page_params.monthly_price

        function update_charged_amount(plan_nickname) {
            $("#charged_amount").text(
                format_money(page_params.seat_count * prices[plan_nickname])
            );
        }

        $('input[type=radio][name=plan]').change(function () {
            update_charged_amount($(this).val());
        });

        $("#autopay_annual_price").text(format_money(prices[page_params.nickname_annual]));
        $("#autopay_annual_price_per_month").text(format_money(prices[page_params.nickname_annual] / 12));
        $("#autopay_monthly_price").text(format_money(prices[page_params.nickname_monthly]));
        $("#invoice_annual_price").text(format_money(prices[page_params.nickname_annual]));
        $("#invoice_annual_price_per_month").text(format_money(prices[page_params.nickname_annual] / 12));
        update_charged_amount($('input[type=radio][name=plan]:checked').val());
    }
});

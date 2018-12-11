$(function () {
    if (window.location.pathname === '/billing/') {
        var stripe_key = $("#payment-method").data("key");
        var card_change_handler = StripeCheckout.configure({ // eslint-disable-line no-undef
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
            card_change_handler.open({
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
    }

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
        var add_card_handler = StripeCheckout.configure({ // eslint-disable-line no-undef
            key: $("#autopay-form").data("key"),
            image: '/static/images/logo/zulip-icon-128x128.png',
            locale: 'auto',
            token: function (stripe_token) {
                function get_form_input(name) {
                    return JSON.stringify($("#autopay-form input[name='" + name + "']").val());
                }

                loading.make_indicator($('#autopay_loading_indicator'),
                                       {text: 'Processing ...', abs_positioned: true});
                $("#autopay-input-section").hide();
                $("#autopay-loading").show();
                $.post({
                    url: "/json/billing/upgrade",
                    data: {
                        stripe_token: JSON.stringify(stripe_token.id),
                        csrfmiddlewaretoken: $("#autopay-form input[name='csrf']").val(),
                        signed_seat_count: get_form_input("signed_seat_count"),
                        salt:  get_form_input("salt"),
                        plan:  get_form_input("plan"),
                        billing_modality:  get_form_input("billing_modality"),
                    },
                    success: function () {
                        $("#autopay-loading").hide();
                        $("#autopay-success").show();
                        location.reload();
                    },
                    error: function (xhr) {
                        $("#autopay-loading").hide();
                        $('#autopay-error').show().text(JSON.parse(xhr.responseText).msg);
                    },
                });
            },
        });

        $('#add-card-button').on('click', function (e) {
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

        var prices = {};
        prices[page_params.nickname_annual] =
            page_params.annual_price * (1 - page_params.percent_off / 100);
        prices[page_params.nickname_monthly] =
            page_params.monthly_price * (1 - page_params.percent_off / 100);

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

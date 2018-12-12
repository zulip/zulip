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

    function get_form_input(form_name, input_name, stringify = true) {
        var input = $("#" + form_name + "-form input[name='" + input_name + "']");
        var val;
        if (input.attr('type') === "radio") {
            val =  $("#" + form_name + "-form input[name='" + input_name + "']:checked").val();
        } else {
            val = input.val();
        }
        if (stringify) {
            return JSON.stringify(val);
        }
        return val;
    }

    if (window.location.pathname === '/upgrade/') {
        var add_card_handler = StripeCheckout.configure({ // eslint-disable-line no-undef
            key: $("#autopay-form").data("key"),
            image: '/static/images/logo/zulip-icon-128x128.png',
            locale: 'auto',
            token: function (stripe_token) {
                loading.make_indicator($('#autopay_loading_indicator'),
                                       {text: 'Processing ...', abs_positioned: true});
                $("#autopay-input-section").hide();
                $('#autopay-error').hide();
                $("#autopay-loading").show();

                var license_management = get_form_input("autopay", "license_management", false);
                $.post({
                    url: "/json/billing/upgrade",
                    data: {
                        stripe_token: JSON.stringify(stripe_token.id),
                        csrfmiddlewaretoken: $("#autopay-form input[name='csrf']").val(),
                        signed_seat_count: get_form_input("autopay", "signed_seat_count"),
                        salt: get_form_input("autopay", "salt"),
                        schedule: get_form_input("autopay", "schedule"),
                        license_management: JSON.stringify(license_management),
                        invoiced_seat_count: $("#" + license_management + "_license_count").val(),
                        billing_modality: get_form_input("autopay", "billing_modality"),
                    },
                    success: function () {
                        $("#autopay-loading").hide();
                        $('#autopay-error').hide();
                        $("#autopay-success").show();
                        location.reload();
                    },
                    error: function (xhr) {
                        $("#autopay-loading").hide();
                        $('#autopay-error').show().text(JSON.parse(xhr.responseText).msg);
                        $("#autopay-input-section").show();
                    },
                });
            },
        });

        $('#add-card-button').on('click', function (e) {
            var license_management = get_form_input("autopay", "license_management", false);
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
            if ($("#invoiced_seat_count")[0].checkValidity() === false) {
                return;
            }
            e.preventDefault();
            loading.make_indicator($('#invoice_loading_indicator'),
                                   {text: 'Processing ...', abs_positioned: true});
            $("#invoice-input-section").hide();
            $('#invoice-error').hide();
            $("#invoice-loading").show();
            $.post({
                url: "/json/billing/upgrade",
                data: {
                    csrfmiddlewaretoken: get_form_input("invoice", "csrfmiddlewaretoken", false),
                    signed_seat_count: get_form_input("invoice", "signed_seat_count"),
                    salt: get_form_input("invoice", "salt"),
                    schedule: get_form_input("invoice", "schedule"),
                    billing_modality: get_form_input("invoice", "billing_modality"),
                    invoiced_seat_count: get_form_input("invoice", "invoiced_seat_count", false),
                },
                success: function () {
                    $("#invoice-loading").hide();
                    $('#invoice-error').hide();
                    $("#invoice-success").show();
                    location.reload();
                },
                error: function (xhr) {
                    $("#invoice-loading").hide();
                    $('#invoice-error').show().text(JSON.parse(xhr.responseText).msg);
                    $("#invoice-input-section").show();
                },
            });
        });

        var prices = {};
        prices.annual = page_params.annual_price * (1 - page_params.percent_off / 100);
        prices.monthly = page_params.monthly_price * (1 - page_params.percent_off / 100);

        function update_charged_amount(schedule) {
            $("#charged_amount").text(
                format_money(page_params.seat_count * prices[schedule])
            );
        }

        function show_license_section(license) {
            $("#license-automatic-section").hide();
            $("#license-manual-section").hide();
            $("#license-mix-section").hide();

            var section_id = "#license-" + license + "-section";
            $(section_id).show();
        }

        $('input[type=radio][name=license_management]').change(function () {
            show_license_section($(this).val());
        });

        $('input[type=radio][name=schedule]').change(function () {
            update_charged_amount($(this).val());
        });

        $("#autopay_annual_price").text(format_money(prices.annual));
        $("#autopay_annual_price_per_month").text(format_money(prices.annual / 12));
        $("#autopay_monthly_price").text(format_money(prices.monthly));
        $("#invoice_annual_price").text(format_money(prices.annual));
        $("#invoice_annual_price_per_month").text(format_money(prices.annual / 12));

        show_license_section($('input[type=radio][name=license_management]:checked').val());
        update_charged_amount($('input[type=radio][name=schedule]:checked').val());
    }
});

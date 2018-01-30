var billingEvents = function () {
    $("body").on("click", ".stripe", function (e) {
        const { key, image, name, email, description } = this.dataset;
        const $this = $(this);

        var handler = StripeCheckout.configure({
            key: key,
            image: image,
            locale: 'auto',
            name: name,
            email: email,
            description: description,
            token: function (token) {
                $.ajax({
                    method: "POST",
                    url: "/billing/",
                    data: {
                        // You can access the token ID with `token.id`.
                        // Get the token ID to your server-side code for use.
                        stripeToken: token.id,
                        csrfmiddlewaretoken: $("[name=csrfmiddlewaretoken]").val(),
                    },
                    dataType: "json",
                    success: () => {
                        // this is to get around the linter in the meanwhile while
                        // we do not have translation support for portico pages.
                        const text = "Add another card";
                        $this.text(text);
                    },
                });
            },
        });

        e.preventDefault();

        // Open Checkout with further options:
        handler.open({
            amount: 0,
        });
    });
};

const load = () => {
    billingEvents();
};

if (document.readyState === "complete") {
    load();
} else {
    $(load);
}

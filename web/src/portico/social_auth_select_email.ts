$(() => {
    $(".choose-email-box").on("click", function () {
        $(this).closest("form").trigger("submit");
    });

    $(".choose-email-box").on("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault(); // prevent page scroll on space
            $(this).closest("form").trigger("submit");
        }
    });
});



$(() => {
    $(".choose-email-box").on("click keypress", function (event) {
        if (
            event.type === "click" ||
            (event.type === "keypress" && (event.key === "Enter" || event.key === " "))
        ) {
            $(this).closest("form").trigger("submit");
        }
    });
});

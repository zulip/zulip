$(function () {
    $('a[data-toggle="tab"]').on('shown', function (e) {
        $("." + $(e.target).data("class")).show();
        $("." + $(e.relatedTarget).data("class")).hide();
    });
});

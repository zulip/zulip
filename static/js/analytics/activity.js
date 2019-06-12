$(function () {
    $('a.envelope-link').click(function () {
        common.copy_data_attribute_value($(this), "admin-emails");
    });
});

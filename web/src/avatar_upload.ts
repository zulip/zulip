import $ from "jquery";

export function display_avatar_upload_complete(
    $container: JQuery = $("#user-avatar-upload-widget").parent(),
): void {
    $container
        .find("#user-avatar-upload-widget .upload-spinner-background")
        .css({visibility: "hidden"});
    $container.find("#user-avatar-upload-widget .image-upload-text").show();
    $container.find("#user-avatar-upload-widget .image-delete-button").show();
}

export function display_avatar_upload_started(
    $container: JQuery = $("#user-avatar-upload-widget").parent(),
): void {
    $container.find("#user-avatar-source").hide();
    $container
        .find("#user-avatar-upload-widget .upload-spinner-background")
        .css({visibility: "visible"});
    $container.find("#user-avatar-upload-widget .image-upload-text").hide();
    $container.find("#user-avatar-upload-widget .image-delete-button").hide();
}

import $ from "jquery";

export const page_params: {
    data_url_suffix: string;
    guest_users: number;
    upload_space_used: number;
} = $("#page-params").data("params");

if (!page_params) {
    throw new Error("Missing page-params");
}

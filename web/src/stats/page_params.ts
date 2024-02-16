import $ from "jquery";

export const page_params: {
    data_url_suffix: string;
    guest_users: number | null;
    upload_space_used: number | null;
} = $("#page-params").data("params");

if (!page_params) {
    throw new Error("Missing page-params");
}

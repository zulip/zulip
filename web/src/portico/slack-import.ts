import {Uppy} from "@uppy/core";
import Dashboard from "@uppy/dashboard";
import Tus from "@uppy/tus";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import {$t} from "../i18n.ts";

$(() => {
    if ($("#slack-import-dashboard").length > 0) {
        const key = $<HTMLInputElement>("#auth_key_for_file_upload").val();
        const uppy = new Uppy({
            autoProceed: true,
            restrictions: {
                maxNumberOfFiles: 1,
                minNumberOfFiles: 1,
                allowedFileTypes: [".zip", "application/zip"],
            },
            meta: {
                key,
            },
            locale: {
                strings: {
                    youCanOnlyUploadFileTypes: $t({
                        defaultMessage: "Upload your Slack export zip file.",
                    }),
                },
                // Copied from
                // https://github.com/transloadit/uppy/blob/d1a3345263b3421a06389aa2e84c66e894b3f29d/packages/%40uppy/utils/src/Translator.ts#L122
                // since we don't want to override the default function.
                // Defining pluralize is required by typescript.
                pluralize(n: number): 0 | 1 {
                    if (n === 1) {
                        return 0;
                    }
                    return 1;
                },
            },
        });
        uppy.use(Dashboard, {
            target: "#slack-import-dashboard",
        });
        uppy.use(Tus, {
            endpoint: "/api/v1/tus/",
            // Allow user to upload the same file multiple times.
            removeFingerprintOnSuccess: true,
        });
        uppy.on("restriction-failed", (_file, error) => {
            $("#slack-import-file-upload-error").text(error.message);
        });
        uppy.on("upload-error", (_file, error) => {
            $("#slack-import-file-upload-error").text(error.message);
        });
        uppy.on("upload-success", (file, _response) => {
            assert(file !== undefined);
            $("#slack-import-start-upload-wrapper").removeClass("hidden");
            $("#slack-import-dashboard-wrapper").addClass("hidden");

            $("#slack-import-uploaded-file-name").text(file.name);
            $("#slack-import-file-upload-error").text("");
            $("#realm-creation-form-slack-import .register-button").prop("disabled", false);
        });

        $(".slack-import-upload-file").on("click", (e) => {
            e.preventDefault();
            e.stopPropagation();

            const dashboard = uppy.getPlugin("Dashboard")!;
            assert(dashboard instanceof Dashboard);
            void dashboard.openModal();
        });
    }

    if ($("#slack-import-poll-status").length > 0) {
        const key = $<HTMLInputElement>("#auth_key_for_polling").val();
        const pollInterval = 2000; // Poll every 2 seconds

        let poll_id: ReturnType<typeof setTimeout> | undefined;
        function checkImportStatus(): void {
            $.get(`/json/realm/import/status/${key}`, {}, (response) => {
                const {status, redirect} = z
                    .object({status: z.string(), redirect: z.optional(z.string())})
                    .parse(response);
                $("#slack-import-poll-status").text(status);
                if (poll_id && redirect !== undefined) {
                    clearInterval(poll_id);
                    window.location.assign(redirect);
                }
            });
        }

        // Start polling
        poll_id = setInterval(checkImportStatus, pollInterval);
    }

    $("#cancel-slack-import").on("click", () => {
        $("#cancel-slack-import-form").trigger("submit");
    });

    $("#slack-access-token").on("input", () => {
        $("#update-slack-access-token").show();
    });
});

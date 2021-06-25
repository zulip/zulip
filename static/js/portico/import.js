import $ from "jquery";

import "@uppy/core/dist/style.css";
import "@uppy/dashboard/dist/style.css";
import {csrf_token} from "./../csrf";

const Uppy = require("@uppy/core");
const Dashboard = require("@uppy/dashboard");
const GoldenRetriever = require("@uppy/golden-retriever");
const DropTarget = require("@uppy/drop-target");
const Tus = require("@uppy/tus");
const AwsS3 = require("@uppy/aws-s3");

const uppy = new Uppy({
    debug: true,
    autoProceed: false,
    restrictions: {
        maxFileSize: 10000000,
        maxNumberOfFiles: 1,
        minNumberOfFiles: 1,
    },
})
    .use(Dashboard, {
        trigger: ".UppyModalOpenerBtn",
        inline: true,
        target: ".DashboardContainer",
        replaceTargetContent: true,
        showProgressDetails: true,
        note: "",
        height: 470,
        metaFields: [
            {id: "name", name: "Name", placeholder: "file name"},
            {id: "caption", name: "Caption", placeholder: ""},
        ],
        browserBackButtonClose: false,
    })
    .use(AwsS3, {
        getUploadParameters(file) {
            return fetch("/json/import/generate_presigned_url", {
                method: "post",
                headers: {
                    accept: "application/json",
                    "content-type": "application/json",
                    "X-CSRFToken": csrf_token,
                },
                body: JSON.stringify({
                    filename: file.name,
                    contentType: file.type,
                }),
            })
                .then((response) => {
                    return response.json();
                })
                .then((data) => {
                    return {
                        method: data.method,
                        url: data.url,
                        fields: data.fields,
                        headers: {
                            "Content-Type": file.type,
                        },
                    };
                });
        },
    })
    .use(DropTarget, {target: document.body})
    .use(GoldenRetriever);

uppy.on("complete", (result) => {
    console.log("successful files:", result.successful);
    console.log("failed files:", result.failed);
});

$(() => {
    console.log("hello");
});

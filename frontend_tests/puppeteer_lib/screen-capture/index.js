"use strict";

const fs = require("fs").promises;
const path = require("path");

let xvfb;
function initXvfb({width, height}) {
    const Xvfb = require("xvfb");
    xvfb = new Xvfb({silent: true, xvfb_args: ["-screen", "0", `${width}x${height}x24`, "-ac"]});
    xvfb.startSync();
}

const launchArgsOptions = [
    "--enable-usermedia-screen-capturing",
    "--allow-http-screen-capture",
    "--auto-select-desktop-capture-source=PuppeteerRecording",
    "--load-extension=" + __dirname,
    "--disable-extensions-except=" + __dirname,
];

async function startRecording(page) {
    await page.evaluate(() => {
        // The document.title set there must be in sync with
        // --auto-select-desktop-capture-source=PuppeteerRecording
        // in launchArgOption above. If the title is not the same,
        // chrome will not auto select this tab when the screen
        // capture permission dialog pops up and the browser will
        // be stuck. We revert back to the old title once we get the
        // screen capture permission.
        const oldTitle = document.title;
        document.title = "PuppeteerRecording";
        window.postMessage({type: "REC_CLIENT_PLAY", data: {oldTitle}}, "*");
    });

    await page.waitForSelector("html.__PuppeteerScreenCapture_recorder_started__");
}

async function stopRecording(page, {filename = null, directory} = {}) {
    if (directory) {
        // This hacky use of page._client to directly use chrome
        // devtools API here is just to avoid creating ~/Downloads
        // directory. If it doesn't work this can be removed and the
        // saving recording to specified path would still work without
        // issues but it will create ~/Downloads or equivalent directory.
        await page._client.send("Page.setDownloadBehavior", {
            behavior: "allow",
            downloadPath: directory,
        });
    }

    await page.evaluate((filename) => {
        window.postMessage({type: "SET_EXPORT_PATH", filename}, "*");
        window.postMessage({type: "REC_STOP"}, "*");
    }, filename);

    if (filename !== null) {
        await page.waitForSelector("html.__PuppeteerScreenCapture_download_complete__");

        const savePath = path.join(directory, filename);
        const downloadPath = await page.evaluate(() => {
            const $html = document.querySelector("html");
            return $html.dataset.puppeteerRecordingFilename;
        });

        try {
            // Remove the old recording it exist!
            await fs.unlink(savePath);
        } catch (e) {
            /* Ignore the error */
        }

        await fs.rename(downloadPath, savePath);
    }

    if (xvfb) {
        xvfb.stopSync();
    }
}

module.exports = {
    launchArgsOptions,
    initXvfb,
    startRecording,
    stopRecording,
};

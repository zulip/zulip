"use strict";

const child_process = require("child_process");

const parallel = process.argv[2];

// Find the files we need to run.
const files = process.argv.slice(3);
if (files.length === 0) {
    throw new Error("No tests found");
}

const index = require.resolve("./index");

function create_file_groups(files, parallel) {
    const group_size = Math.ceil(files.length / parallel);
    const file_groups = [];
    for (let i = 0; i < parallel; i += 1) {
        const file_group = files.slice(i * group_size, (i + 1) * group_size);
        // never generate an empty group or send it to a forked process.
        if (file_group.length > 0) {
            file_groups.push(file_group);
        }
    }
    return file_groups;
}

const file_groups = create_file_groups(files, parallel);

for (const file_group of file_groups) {
    const worker_process = child_process.fork(index, file_group, {stdio: "inherit"});
    worker_process.on("error", (error) => {
        console.error(error);
        // if we fail to create a child processes, send a non zero
        // return code, so that we don't check coverage
        process.exitCode = 2;
    });
    worker_process.on("exit", (code) => {
        if (code === undefined || code !== 0) {
            // if any worker_process ends without running all its test
            // files eg due to an error, send a non zero return code,
            // so that we don't check coverage
            process.exitCode = 1;
        }
    });
}

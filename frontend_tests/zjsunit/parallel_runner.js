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

const worker_processes = [];

// we use this map to ensure that we only call .kill() on the processes
// we have forked, this is important because if we didn't ensure this,
// it is entirely possible that we would send a kill signal to an
// arbitrary process which just happens to have the same pid as the one
// we had created (through pid reallocation).
// see: https://nodejs.org/api/child_process.html#subprocesskillsignal
const has_exited = new Map();

function kill_all_child_processes() {
    for (const worker_process of worker_processes) {
        if (!has_exited.get(worker_process.pid)) {
            has_exited.set(worker_process.pid, true);
            worker_process.kill();
        }
    }
}

for (const file_group of file_groups) {
    const worker_process = child_process.fork(index, file_group, {stdio: "inherit"});
    const current_pid = worker_process.pid;
    has_exited.set(current_pid, false);
    worker_process.on("error", (error) => {
        console.error(error);
        // if we fail to create a child processes, kill all previously
        // created processes, exit this process and send a non zero
        // return code, so that we don't check coverage
        has_exited.set(current_pid, true);
        kill_all_child_processes();
        process.exit(2);
    });
    worker_process.on("exit", (code) => {
        has_exited.set(current_pid, true);
        if (code === undefined || code !== 0) {
            // if any worker_process ends without running all its test
            // files eg due to an error, then kill all worker_processes,
            // exit this process and send a non zero return code, so that
            // we don't check coverage
            kill_all_child_processes();
            process.exit(1);
        }
    });
    worker_processes.push(worker_process);
}

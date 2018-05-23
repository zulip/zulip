const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const { split_array } = require('./utils');
const finder = require('./finder');
const test_files = finder.find_files_to_run();
if (test_files.length === 0) {
    throw "No tests found";
}

let parallelism = 2 || os.cpus().length;
let test_files_array;
if (test_files.length <= parallelism) {
    test_files.forEach(file => {
       test_files_array.push([file]);
    });
} else {
    test_files_array = split_array(test_files, parallelism);
}

if (test_files.length < parallelism) {
    parallelism = test_files.length;
}

const exit_codes = [];
const test_runner_path = path.join(__dirname, 'test_runner.js');
for (let i = 0; i < parallelism; i++) {
    const test_runner = spawn(process.execPath, [test_runner_path], {
       stdio: 'inherit',
       env: {
           ...process.env,
           ZTEST_FILES: JSON.stringify(test_files_array[i])
       }
    });

    test_runner.on('exit', (code) => {
        exit_codes.push(code);

        if (exit_codes.length === parallelism) {
            const exit_code = exit_codes.includes(1) ? 1 : 0;
            process.exit(exit_code);
        }
    });
}

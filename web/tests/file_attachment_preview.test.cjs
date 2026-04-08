"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {initialize_user_settings} = zrequire("user_settings");

// Initialize with empty file_preview_extensions (default — built-in set is always active)
const user_settings = {file_preview_extensions: ""};
initialize_user_settings({user_settings});

const file_attachment_preview = zrequire("file_attachment_preview");

run_test("should_preview matches built-in extensions with empty setting", () => {
    // Built-in types are always previewable when setting is empty (default)
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.txt"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.md"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.py"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.csv"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.pdf"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.rs"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.go"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.js"), true);
});

run_test("should_preview is case insensitive for URL extensions", () => {
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.TXT"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.Md"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.PY"), true);
});

run_test("should_preview rejects non-matching extensions", () => {
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.jpg"), false);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.png"), false);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.zip"), false);
});

run_test("should_preview matches pdf extension", () => {
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.pdf"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.PDF"), true);
});

run_test("should_preview rejects files without extensions", () => {
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/Makefile"), false);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file"), false);
});

run_test("should_preview handles encoded filenames", () => {
    assert.equal(
        file_attachment_preview.should_preview("/user_uploads/1/ab/my%20file.txt"),
        true,
    );
    assert.equal(
        file_attachment_preview.should_preview("/user_uploads/1/ab/my%20file.jpg"),
        false,
    );
});

run_test("should_preview includes extra extensions from setting", () => {
    // Add custom extra extensions
    user_settings.file_preview_extensions = "log,conf,env";
    // Extra extensions are previewable
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.log"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.conf"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.env"), true);
    // Built-in types still work
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.py"), true);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.md"), true);
    // Unknown extensions still rejected
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.jpg"), false);

    // Reset
    user_settings.file_preview_extensions = "";
});

run_test("should_preview none disables all previews", () => {
    user_settings.file_preview_extensions = "none";
    // Even built-in types are disabled
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.txt"), false);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.md"), false);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.py"), false);
    assert.equal(file_attachment_preview.should_preview("/user_uploads/1/ab/file.pdf"), false);

    // Reset
    user_settings.file_preview_extensions = "";
});

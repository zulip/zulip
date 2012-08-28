"use strict";

const assert = require("node:assert/strict");

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

mock_esm("../generated/supported_browser_regex.ts", {
    // Snapshot of generated regex on 2025-12-17
    baselineBrowserRegex:
        /Edge?\/(1{2}[1-9]|1[2-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|Firefox\/(1{2}[4-9]|1[2-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|Chrom(ium|e)\/(1{2}[1-9]|1[2-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|(Maci|X1{2}).+ Version\/(16\.([4-9]|\d{2,})|(1[7-9]|[2-9]\d|\d{3,})\.\d+)([,.]\d+|)( \(\w+\)|)( Mobile\/\w+|) Safari\/|Chrome.+OPR\/(9[7-9]|\d{3,})\.\d+\.\d+|(CPU[ +]OS|iPhone[ +]OS|CPU[ +]iPhone|CPU IPhone OS|CPU iPad OS)[ +]+(16[._]([4-9]|\d{2,})|(1[7-9]|[2-9]\d|\d{3,})[._]\d+)([._]\d+|)|Android:?[ /-](14[2-9]|1[5-9]\d|[2-9]\d{2}|\d{4,})(\.\d+|)(\.\d+|)|Mobile Safari.+OPR\/([89]\d|\d{3,})\.\d+\.\d+|Android.+Firefox\/(14[4-9]|1[5-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|Android.+Chrom(ium|e)\/(14[2-9]|1[5-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|SamsungBrowser\/(2[2-9]|[3-9]\d|\d{3,})\.\d+/,
    allBrowsersRegex:
        /IE (5\.5|[67]\.0)|Trident\/4\.0|Trident\/5\.0|Trident\/6\.0|Trident\/[78]\.0|Edge?\/(1[2-9]|[2-9]\d|\d{3,})\.\d+(\.\d+|)|Firefox\/([2-9]|\d{2,})\.\d+(\.\d+|)|Chrom(ium|e)\/([4-9]|\d{2,})\.\d+(\.\d+|)([\d.]+$|.*Safari\/(?![\d.]+ Edge\/[\d.]+$))|(Maci|X1{2}).+ Version\/(3\.([1-9]|\d{2,})|([4-9]|\d{2,})\.\d+)([,.]\d+|)( \(\w+\)|)( Mobile\/\w+|) Safari\/|Opera\/9\.80.+Version\/(9\.0|9\.[56]|10\.[01]|10\.[56]|1{2}\.[01]|1{2}\.[56]|12\.[01])(\.\d+|)|Chrome.+OPR\/(1[5-9]|[2-9]\d|\d{3,})\.\d+\.\d+|[^e] (CPU[ +]OS|iPhone[ +]OS|CPU[ +]iPhone|CPU IPhone OS|CPU iPad OS)[ +]+(3[._]([2-9]|\d{2,})|([4-9]|\d{2,})[._]\d+)([._]\d+|)|Opera Mini|Android Eclair|Android Froyo|Android Gingerbread|Android Honeycomb|Android:?[ /-](2(\.([1-9]|\d{2,})|)|([3-9]|\d{2,})(\.\d+|))(\.\d+|);(?! ARM; Trident)|(Black[Bb]er{2}y|B{2}10).+Version\/([7-9]|\d{2,})\.\d+\.\d+|Opera\/.+Opera Mobi.+Version\/(1[01]\.0|1{2}\.1|1{2}\.5|12\.[01])|Mobile Safari.+OPR\/([89]\d|\d{3,})\.\d+\.\d+|Android.+Firefox\/(14[4-9]|1[5-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|Android.+Chrom(ium|e)\/(14[2-9]|1[5-9]\d|[2-9]\d{2}|\d{4,})\.\d+(\.\d+|)|IEMobile[ /]([1-9]\d|\d{3,})\.\d+|Android.+(UC? ?Browser|UCWEB|U3)[ /]?(15\.([5-9]|\d{2,})|(1[6-9]|[2-9]\d|\d{3,})\.\d+)\.\d+|SamsungBrowser\/([4-9]|\d{2,})\.\d+|Android.+MQ{2}Browser\/(14(\.(9|\d{2,})|)|(1[5-9]|[2-9]\d|\d{3,})(\.\d+|))(\.\d+|)|baidubrowser[\s/](13(\.(5[2-9]|[6-9]\d|\d{3,})|)|(1[4-9]|[2-9]\d|\d{3,})(\.\d+|))(\.\d+|)|K[Aa][Ii]OS\/(2\.([5-9]|\d{2,})|([3-9]|\d{2,})\.\d+)(\.\d+|)/,
});
const {is_browser_unsupported_old_version} = zrequire("browser_support");

run_test("browser present in baseline browsers is supported", () => {
    window.navigator.userAgent = "Chrome/129.0.1132.57";
    assert.equal(is_browser_unsupported_old_version(), false);
});

run_test("browser present in all browsers but not in baseline browsers is unsupported", () => {
    window.navigator.userAgent = "Chrome/20.0.1132.57";
    assert.equal(is_browser_unsupported_old_version(), true);
});

run_test("browser not present in all browsers is skipped for checking", () => {
    window.navigator.userAgent = "ExerimentalBrowser/20.0.1132.57";
    assert.equal(is_browser_unsupported_old_version(), false);
});

run_test("future versions of a browser are supported", () => {
    window.navigator.userAgent = "Chrome/1000.0.1132.57";
    assert.equal(is_browser_unsupported_old_version(), false);
});

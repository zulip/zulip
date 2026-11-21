"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {get_email_suggestion} = zrequire("email_suggestion");

run_test("suggests a fix for misspelled provider domains", () => {
    const misspelled_domains = [
        ["gamil.com", "gmail.com"],
        ["gmial.com", "gmail.com"],
        ["gmail.con", "gmail.com"],
        ["gmai.com", "gmail.com"],
        ["gnail.com", "gmail.com"],
        ["gmil.com", "gmail.com"],
        ["gmail.cm", "gmail.com"],
        ["gmail.om", "gmail.com"],
        ["hotmal.com", "hotmail.com"],
        ["hotmai.com", "hotmail.com"],
        ["hotmial.com", "hotmail.com"],
        ["yaho.com", "yahoo.com"],
        ["yahho.com", "yahoo.com"],
        ["yahooo.com", "yahoo.com"],
        ["outlok.com", "outlook.com"],
        ["icloud.con", "icloud.com"],
        ["icloud.co", "icloud.com"],
        ["yahho.co.in", "yahoo.co.in"],
        ["hotmial.co.uk", "hotmail.co.uk"],
        ["yaho.co.in", "yahoo.co.in"],
        ["hotmal.co.in", "hotmail.co.in"],
        ["outlok.in", "outlook.in"],
        ["yahooo.com.np", "yahoo.com.np"],
        ["hotmial.com.bd", "hotmail.com.bd"],
        ["outlok.com.au", "outlook.com.au"],
        ["yaho.com.br", "yahoo.com.br"],
        ["hotmal.co.jp", "hotmail.co.jp"],
        ["redifmail.com", "rediffmail.com"],
        ["rediffmial.com", "rediffmail.com"],
    ];
    for (const [domain, expected] of misspelled_domains) {
        assert.equal(get_email_suggestion(`test@${domain}`), `test@${expected}`, domain);
    }
});

run_test("keeps the part before the @ and ignores surrounding spaces", () => {
    assert.equal(get_email_suggestion("Test.Name+tag@gamil.com"), "Test.Name+tag@gmail.com");
    assert.equal(get_email_suggestion("first.last2025@gmial.com"), "first.last2025@gmail.com");
    assert.equal(get_email_suggestion("  test@gamil.com "), "test@gmail.com");
    assert.equal(get_email_suggestion("test@GAMIL.COM"), "test@gmail.com");
});

run_test("makes no suggestion for valid domains", () => {
    const valid_domains = [
        "iitb.ac.in iisc.ac.in du.ac.in jnu.ac.in iem.edu.in nitt.edu mit.edu stanford.edu",
        "ox.ac.uk cam.ac.uk ucl.ac.uk unimelb.edu.au usp.br u-tokyo.ac.jp snu.ac.kr",
        "tsinghua.edu.cn uct.ac.za nus.edu.sg utoronto.ca ethz.ch tu.edu.np buet.ac.bd",
        "pu.edu.pk cmb.ac.lk chula.ac.th um.edu.my up.edu.ph ui.ac.id vnu.edu.vn cu.edu.eg",
        "unam.mx tau.ac.il auckland.ac.nz nasa.gov nih.gov india.gov.in nic.in isro.gov.in",
        "rbi.org.in gov.uk nhs.uk gov.au gov.br gob.mx gouv.fr admin.ch gov.za gov.sg go.jp",
        "go.kr gov.cn gov.np gov.bd gov.pk gov.lk go.th gov.ph go.id gov.vn gov.ae gov.il",
        "canada.ca govt.nz europa.eu un.org google.com apple.com microsoft.com amazon.com",
        "meta.com ibm.com intel.com amd.com nvidia.com sap.com adobe.com hp.com lg.com",
        "tcs.com infosys.com wipro.com zoho.com flipkart.com paytm.com tata.co.in sbi.co.in",
        "bbc.co.uk toyota.co.jp petrobras.com.br telstra.com.au mtn.co.za siemens.com web.de",
        "aol.com msn.com live.com me.com mac.com gmx.net proton.me aim.com cox.net att.net",
        "yahoo.com hotmail.com outlook.com yahoo.co.in hotmail.co.uk outlook.in comcast.net",
        "verizon.net sbcglobal.net bellsouth.net earthlink.net btinternet.com optonline.net",
    ].flatMap((line) => line.split(" "));
    for (const domain of valid_domains) {
        assert.equal(get_email_suggestion(`test@${domain}`), undefined, domain);
    }
    assert.equal(get_email_suggestion("TEST@GMAIL.COM"), undefined);
});

run_test("makes no suggestion for any name with any country ending", () => {
    const names = ["company", "shop", "kumar", "ibm", "web", "acme"];
    const endings = [
        "com net org in co.in ac.in edu.in gov.in uk co.uk ac.uk au com.au br com.br jp co.jp",
        "kr cn za co.za ng ke np com.np bd com.bd pk lk th ph my sg id vn de fr it es pt nl",
        "se no fi pl ru tr il ae sa eg mx ar cl co ca nz ie ch at be dk cz gr hk tw io ai dev",
        "me tv edu gov",
    ].flatMap((line) => line.split(" "));
    for (const name of names) {
        for (const ending of endings) {
            const domain = `${name}.${ending}`;
            assert.equal(get_email_suggestion(`test@${domain}`), undefined, domain);
        }
    }
});

run_test("makes no suggestion for malformed input", () => {
    for (const input of ["", "test", "test@", "@gmail.com", "test@@gamil.com"]) {
        assert.equal(get_email_suggestion(input), undefined, input);
    }
});

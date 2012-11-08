/*global casper*/
/*jshint strict:false*/
casper.start('tests/site/form.html', function() {
    this.test.comment('Casper.fill()');
    this.fill('form[action="result.html"]', {
        email:         'chuck@norris.com',
        password:      'chuck',
        content:       'Am watching thou',
        check:         true,
        choice:        'no',
        topic:         'bar',
        file:          phantom.libraryPath + '/README.md',
        'checklist[]': ['1', '3']
    });
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="email"]').value;
    }, 'chuck@norris.com', 'Casper.fill() can fill an input[type=text] form field');
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="password"]').value;
    }, 'chuck', 'Casper.fill() can fill an input[type=password] form field');
    this.test.assertEvalEquals(function() {
        return document.querySelector('textarea[name="content"]').value;
    }, 'Am watching thou', 'Casper.fill() can fill a textarea form field');
    this.test.assertEvalEquals(function() {
        return document.querySelector('select[name="topic"]').value;
    }, 'bar', 'Casper.fill() can pick a value from a select form field');
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="check"]').checked;
    }, true, 'Casper.fill() can check a form checkbox');
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="choice"][value="no"]').checked;
    }, true, 'Casper.fill() can check a form radio button 1/2');
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="choice"][value="yes"]').checked;
    }, false, 'Casper.fill() can check a form radio button 2/2');
    this.test.assertEvalEquals(function() {
        return document.querySelector('input[name="file"]').files.length === 1;
    }, true, 'Casper.fill() can select a file to upload');
    this.test.assertEvalEquals(function() {
        return (document.querySelector('input[name="checklist[]"][value="1"]').checked &&
               !document.querySelector('input[name="checklist[]"][value="2"]').checked &&
                document.querySelector('input[name="checklist[]"][value="3"]').checked);
    }, true, 'Casper.fill() can fill a list of checkboxes');
    this.click('input[type="submit"]');
});

casper.then(function() {
    this.test.comment('Form submitted');
    this.test.assertUrlMatch(/email=chuck@norris.com/, 'Casper.fill() input[type=email] field was submitted');
    this.test.assertUrlMatch(/password=chuck/, 'Casper.fill() input[type=password] field was submitted');
    this.test.assertUrlMatch(/content=Am\+watching\+thou/, 'Casper.fill() textarea field was submitted');
    this.test.assertUrlMatch(/check=on/, 'Casper.fill() input[type=checkbox] field was submitted');
    this.test.assertUrlMatch(/choice=no/, 'Casper.fill() input[type=radio] field was submitted');
    this.test.assertUrlMatch(/topic=bar/, 'Casper.fill() select field was submitted');
});

casper.thenOpen('tests/site/form.html', function() {
    this.test.comment('Unexistent fields');
    this.test.assertRaises(this.fill, ['form[action="result.html"]', {
        unexistent: 42
    }, true], 'Casper.fill() raises an exception when unable to fill a form');
});

// multiple forms
casper.thenOpen('tests/site/multiple-forms.html', function() {
    this.test.comment('Multiple forms');
    this.fill('form[name="f2"]', {
        yo: "ok"
    }, true);
});

casper.then(function() {
    this.test.assertUrlMatch(/\?f=f2&yo=ok$/, 'Casper.fill() handles multiple forms');
});

casper.run(function() {
    this.test.done();
});

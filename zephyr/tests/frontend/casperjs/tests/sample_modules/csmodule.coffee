try
  exports.ok = true
catch e
  casper.test.fail('error in coffeescript module code: ' + e)
  casper.test.done()

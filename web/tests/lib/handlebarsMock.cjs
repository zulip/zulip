// Simple mock for Handlebars templates in Jest tests.
// The real renderers are functions that accept data and return HTML.
module.exports = function mockTemplate() {
  return function () {
    return '';
  };
};

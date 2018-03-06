# UI: Input Pills

This is a high level and API explanation of the input pill interface in the
frontend of the Zulip web application.

## Setup

A pill container should have the following markup:

```html
<div class="pill-container">
    <div class="input" contenteditable="true"></div>
</div>
```

The pills will automatically be inserted in before the ".input" in order.

## Basic Usage

```js
var pill_containter = $("#input_container");
var pills = input_pill.create({
    container: pill_container,
    create_item_from_text: user_pill.create_item_from_email,
    get_text_from_item: user_pill.get_email_from_item,
});
```

You can look at `static/js/user_pill.js` to see how the above
methods are implemented.  Essentially you just need to convert
from raw data (like an email) to structured data (like an object
with display_value, email, and user_id for a user), and vice
versa.  The most important field to supply is `display_value`.
For user pills `pill_item.display_value === user.full_name`.

## Typeahead

Pills almost always work in conjunction with typeahead, and
you will want to provide a `source` function to typeahead
that can exclude items from the prior pills.  Here is an
example snippet from our user group settings code.

```js
source: function () {
    return user_pill.typeahead_source(pills);
},
```

And then in `user_pill.js`...

```js
exports.typeahead_source = function (pill_widget) {
    var items = people.get_realm_persons();
    var taken_user_ids = exports.get_user_ids(pill_widget);
    items = _.filter(items, function (item) {
        return taken_user_ids.indexOf(item.user_id) === -1;
    });
    return items;
};
```

### `onPillCreate` and `onPillRemove` methods

You can get notifications from the pill code that pills have been
created/remove.


```js
pills.onPillCreate(function () {
    update_save_state();
});

pills.onPillRemove(function () {
    update_save_state();
});
```

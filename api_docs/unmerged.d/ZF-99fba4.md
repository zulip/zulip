* [`GET /events`](/api/get-events): Events with `type: "navigation_view"` are
  sent to the user when a navigation view is created, updated, or removed.

* [`POST /register`](/api/register-queue): Added `navigation_views` field in
  response.

* [`GET /navigation_views`](/api/get-navigation-views): Added a new endpoint for
  fetching all navigation views of the user.

* [`POST /navigation_views`](/api/add-navigation-view): Added a new endpoint for
  creating a new navigation view.

* [`PATCH /navigation_views/{fragment}`](/api/edit-navigation-view): Added a new
  endpoint for editing the details of a navigation view.

* [`DELETE /navigation_views/{fragment}`](/api/remove-navigation-view): Added a new
  endpoint for removing a navigation view.

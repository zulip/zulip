# FourSquare Bot

* This is a bot that returns a list of restaurants from a user input of location,
proximity and restaurant type in that exact order. The number of returned
restaurants are capped at 3 per request.

* The list of restaurants are brought to Zulip using an API. The bot sends a GET
request to https://api.foursquare.com/v2/. If the user does not correctly input
a location, proximity and a restaurant type, the bot will return an error message.

* For example, if the user says "@foursquare 'Chicago, IL' 80000 seafood", the bot
will return:

Food nearby 'Chicago, IL' coming right up:

    Dee's Seafood Co.
    2723 S Poplar Ave, Chicago, IL 60608, United States
    Fish Markets

    Seafood Harbor
    2131 S Archer Ave (at Wentworth Ave), Chicago, IL 60616, United States
    Seafood Restaurants

    Joe's Seafood, Prime Steak & Stone Crab
    60 E Grand Ave (at N Rush St), Chicago, IL 60611, United States
    Seafood Restaurants

* If the user enters a wrong word, like "@foursquare 80000 donuts" or "@foursquare",
then an error message saying invalid input will be displayed.

* To get the required API key, visit: https://developer.foursquare.com/overview/auth
for more information.

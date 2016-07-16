from __future__ import absolute_import
from __future__ import unicode_literals

from six import text_type
from typing import Any, Dict, Optional
import ujson


NORMAL_TWEET = """{
  "created_at": "Sat Sep 10 22:23:38 +0000 2011",
  "id_str": "112652479837110273",
  "in_reply_to_user_id_str": "783214",
  "text": "@twitter meets @seepicturely at #tcdisrupt cc.@boscomonkey @episod http://t.co/6J2EgYM",
  "source": "<a href=\\"http://instagram.com\\" rel=\\"nofollow\\">Instagram</a>",
  "lang": "en",
  "id": 112652479837110273,
  "in_reply_to_user_id": 783214,
  "favorite_count": 3,
  "hashtags": [
    {
      "text": "tcdisrupt"
    }
  ],
  "user": {
    "profile_sidebar_fill_color": "efefef",
    "name": "Eoin McMillan ",
    "profile_image_url": "http://a1.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
    "created_at": "Mon May 16 20:07:59 +0000 2011",
    "location": "Twitter",
    "profile_link_color": "009999",
    "id_str": "299862462",
    "favourites_count": 0,
    "url": "http://www.eoin.me",
    "id": 299862462,
    "utc_offset": null,
    "profile_image_url_https": "https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
    "listed_count": 0,
    "followers_count": 9,
    "lang": "en",
    "profile_text_color": "333333",
    "profile_background_image_url_https": "https://si0.twimg.com/images/themes/theme14/bg.gif",
    "description": "Eoin's photography account. See @mceoin for tweets.",
    "geo_enabled": false,
    "profile_background_color": "131516",
    "time_zone": null,
    "statuses_count": 255,
    "friends_count": 0,
    "profile_background_image_url": "http://a1.twimg.com/images/themes/theme14/bg.gif",
    "screen_name": "imeoin",
    "statuses_count": 270
  },
  "user_mentions": [
    {
      "screen_name": "twitter",
      "name": "Twitter",
      "id": 1
    },
    {
      "screen_name": "boscomonkey",
      "name": "Bosco So",
      "id": 2
    },
    {
      "screen_name": "episod",
      "name": "Taylor Singletary",
      "id": 3
    }
   ],
  "urls": [
    {
      "expanded_url": "http://instagram.com/p/MuW67/",
      "url": "http://t.co/6J2EgYM"
    }
  ]
}"""

MENTION_IN_LINK_TWEET = """{
  "created_at": "Sat Sep 10 22:23:38 +0000 2011",
  "id_str": "112652479837110273",
  "in_reply_to_user_id_str": "783214",
  "text": "http://t.co/@foo",
  "source": "<a href=\\"http://twitter.com\\" rel=\\"nofollow\\">Twitter Web Client</a>",
  "lang": "en",
  "id": 112652479837110273,
  "in_reply_to_user_id": 783214,
  "favorite_count": 3,
  "user": {
    "profile_sidebar_fill_color": "efefef",
    "name": "Eoin McMillan ",
    "profile_image_url": "http://a1.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
    "created_at": "Mon May 16 20:07:59 +0000 2011",
    "location": "Twitter",
    "profile_link_color": "009999",
    "id_str": "299862462",
    "favourites_count": 0,
    "url": "http://www.eoin.me",
    "id": 299862462,
    "utc_offset": null,
    "profile_image_url_https": "https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
    "listed_count": 0,
    "followers_count": 9,
    "lang": "en",
    "profile_text_color": "333333",
    "profile_background_image_url_https": "https://si0.twimg.com/images/themes/theme14/bg.gif",
    "description": "Eoin's photography account. See @mceoin for tweets.",
    "geo_enabled": false,
    "profile_background_color": "131516",
    "time_zone": null,
    "statuses_count": 255,
    "friends_count": 0,
    "profile_background_image_url": "http://a1.twimg.com/images/themes/theme14/bg.gif",
    "screen_name": "imeoin",
    "statuses_count": 270
  },
  "user_mentions": [
    {
      "screen_name": "foo",
      "name": "Foo",
      "id": 1
    }
   ],
  "urls": [
    {
      "expanded_url": "http://foo.com",
      "url": "http://t.co/@foo"
    }
  ]
}"""

MEDIA_TWEET = """{
  "created_at": "Sat Sep 10 22:23:38 +0000 2011",
  "id_str": "112652479837110273",
  "in_reply_to_user_id_str": "783214",
  "text": "http://t.co/xo7pAhK6n3",
  "source": "<a href=\\"http://twitter.com\\" rel=\\"nofollow\\">Twitter Web Client</a>",
  "lang": "en",
  "id": 112652479837110273,
  "in_reply_to_user_id": 783214,
  "favorite_count": 3,
  "user": {
    "profile_sidebar_fill_color": "efefef",
    "name": "Eoin McMillan ",
    "profile_image_url": "http://a1.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
    "created_at": "Mon May 16 20:07:59 +0000 2011",
    "location": "Twitter",
    "profile_link_color": "009999",
    "id_str": "299862462",
    "favourites_count": 0,
    "url": "http://www.eoin.me",
    "id": 299862462,
    "utc_offset": null,
    "profile_image_url_https": "https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
    "listed_count": 0,
    "followers_count": 9,
    "lang": "en",
    "profile_text_color": "333333",
    "profile_background_image_url_https": "https://si0.twimg.com/images/themes/theme14/bg.gif",
    "description": "Eoin's photography account. See @mceoin for tweets.",
    "geo_enabled": false,
    "profile_background_color": "131516",
    "time_zone": null,
    "statuses_count": 255,
    "friends_count": 0,
    "profile_background_image_url": "http://a1.twimg.com/images/themes/theme14/bg.gif",
    "screen_name": "imeoin",
    "statuses_count": 270
  },
  "media": [
    {
      "display_url": "pic.twitter.com/xo7pAhK6n3",
      "expanded_url": "http://twitter.com/NEVNBoston/status/421654515616849920/photo/1",
      "id": 421654515495211010,
      "media_url": "http://pbs.twimg.com/media/BdoEjD4IEAIq86Z.jpg",
      "media_url_https": "https://pbs.twimg.com/media/BdoEjD4IEAIq86Z.jpg",
      "sizes": {"large": {"h": 700, "resize": "fit", "w": 1024},
                 "medium": {"h": 410, "resize": "fit", "w": 599},
                 "small": {"h": 232, "resize": "fit", "w": 340},
                 "thumb": {"h": 150, "resize": "crop", "w": 150}},
      "type": "photo",
      "url": "http://t.co/xo7pAhK6n3"}
  ]
}"""


def twitter(tweet_id):
    # type: (text_type) -> Optional[Dict[text_type, Any]]
    if tweet_id in ["112652479837110273", "287977969287315456", "287977969287315457"]:
        return ujson.loads(NORMAL_TWEET)
    elif tweet_id == "287977969287315458":
        return ujson.loads(MENTION_IN_LINK_TWEET)
    elif tweet_id == "287977969287315459":
        return ujson.loads(MEDIA_TWEET)
    else:
        return None

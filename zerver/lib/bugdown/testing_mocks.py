# -*- coding: utf-8 -*-

from typing import Any, Dict, Optional
import ujson


NORMAL_TWEET = """{
    "created_at": "Sat Sep 10 22:23:38 +0000 2011",
    "favorite_count": 1,
    "full_text": "@twitter meets @seepicturely at #tcdisrupt cc.@boscomonkey @episod http://t.co/6J2EgYM",
    "hashtags": [
        {
            "text": "tcdisrupt"
        }
    ],
    "id": 112652479837110270,
    "id_str": "112652479837110273",
    "in_reply_to_screen_name": "Twitter",
    "in_reply_to_user_id": 783214,
    "lang": "en",
    "retweet_count": 4,
    "source": "<a href=\\"http://instagram.com\\" rel=\\"nofollow\\">Instagram</a>",
    "urls": [
        {
            "expanded_url": "http://instagr.am/p/MuW67/",
            "url": "http://t.co/6J2EgYM"
        }
    ],
    "user": {
        "created_at": "Mon May 16 20:07:59 +0000 2011",
        "description": "Eoin's photography account. See @mceoin for tweets.",
        "followers_count": 3,
        "id": 299862462,
        "lang": "en",
        "location": "Twitter",
        "name": "Eoin McMillan",
        "profile_background_color": "131516",
        "profile_background_image_url": "http://abs.twimg.com/images/themes/theme14/bg.gif",
        "profile_background_tile": true,
        "profile_image_url": "http://pbs.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
        "profile_link_color": "009999",
        "profile_sidebar_fill_color": "EFEFEF",
        "profile_text_color": "333333",
        "screen_name": "imeoin",
        "statuses_count": 278,
        "url": "http://t.co/p9hKpiGMyN"
    },
    "user_mentions": [
        {
            "id": 783214,
            "name": "Twitter",
            "screen_name": "Twitter"
        },
        {
            "id": 14792670,
            "name": "Bosco So",
            "screen_name": "boscomonkey"
        },
        {
            "id": 819797,
            "name": "Taylor Singletary",
            "screen_name": "episod"
        }
    ]
}"""

MENTION_IN_LINK_TWEET = """{
    "created_at": "Sat Sep 10 22:23:38 +0000 2011",
    "favorite_count": 1,
    "full_text": "http://t.co/@foo",
    "hashtags": [
        {
            "text": "tcdisrupt"
        }
    ],
    "id": 112652479837110270,
    "id_str": "112652479837110273",
    "in_reply_to_screen_name": "Twitter",
    "in_reply_to_user_id": 783214,
    "lang": "en",
    "retweet_count": 4,
    "source": "<a href=\\"http://instagram.com\\" rel=\\"nofollow\\">Instagram</a>",
    "urls": [
      {
        "expanded_url": "http://foo.com",
        "url": "http://t.co/@foo"
      }
    ],
    "user": {
        "created_at": "Mon May 16 20:07:59 +0000 2011",
        "description": "Eoin's photography account. See @mceoin for tweets.",
        "followers_count": 3,
        "id": 299862462,
        "lang": "en",
        "location": "Twitter",
        "name": "Eoin McMillan",
        "profile_background_color": "131516",
        "profile_background_image_url": "http://abs.twimg.com/images/themes/theme14/bg.gif",
        "profile_background_tile": true,
        "profile_image_url": "http://pbs.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
        "profile_link_color": "009999",
        "profile_sidebar_fill_color": "EFEFEF",
        "profile_text_color": "333333",
        "screen_name": "imeoin",
        "statuses_count": 278,
        "url": "http://t.co/p9hKpiGMyN"
    },
    "user_mentions": [
        {
            "id": 783214,
            "name": "Foo",
            "screen_name": "foo"
        }
    ]
}"""

MEDIA_TWEET = """{
    "created_at": "Sat Sep 10 22:23:38 +0000 2011",
    "favorite_count": 1,
    "full_text": "http://t.co/xo7pAhK6n3",
    "id": 112652479837110270,
    "id_str": "112652479837110273",
    "in_reply_to_screen_name": "Twitter",
    "in_reply_to_user_id": 783214,
    "lang": "en",
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
    ],
    "retweet_count": 4,
    "source": "<a href=\\"http://instagram.com\\" rel=\\"nofollow\\">Instagram</a>",
    "user": {
        "created_at": "Mon May 16 20:07:59 +0000 2011",
        "description": "Eoin's photography account. See @mceoin for tweets.",
        "followers_count": 3,
        "id": 299862462,
        "lang": "en",
        "location": "Twitter",
        "name": "Eoin McMillan",
        "profile_background_color": "131516",
        "profile_background_image_url": "http://abs.twimg.com/images/themes/theme14/bg.gif",
        "profile_background_tile": true,
        "profile_image_url": "http://pbs.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
        "profile_link_color": "009999",
        "profile_sidebar_fill_color": "EFEFEF",
        "profile_text_color": "333333",
        "screen_name": "imeoin",
        "statuses_count": 278,
        "url": "http://t.co/p9hKpiGMyN"
    },
    "user_mentions": [
        {
            "id": 783214,
            "name": "Foo",
            "screen_name": "foo"
        }
    ]
}"""

EMOJI_TWEET = """{
    "created_at": "Sat Sep 10 22:23:38 +0000 2011",
    "favorite_count": 1,
    "full_text": "Zulip is 💯% open-source!",
    "hashtags": [
        {
            "text": "tcdisrupt"
        }
    ],
    "id": 112652479837110270,
    "id_str": "112652479837110273",
    "in_reply_to_screen_name": "Twitter",
    "in_reply_to_user_id": 783214,
    "lang": "en",
    "retweet_count": 4,
    "source": "<a href=\\"http://instagram.com\\" rel=\\"nofollow\\">Instagram</a>",
    "user": {
        "created_at": "Mon May 16 20:07:59 +0000 2011",
        "description": "Eoin's photography account. See @mceoin for tweets.",
        "followers_count": 3,
        "id": 299862462,
        "lang": "en",
        "location": "Twitter",
        "name": "Eoin McMillan",
        "profile_background_color": "131516",
        "profile_background_image_url": "http://abs.twimg.com/images/themes/theme14/bg.gif",
        "profile_background_tile": true,
        "profile_image_url": "http://pbs.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png",
        "profile_link_color": "009999",
        "profile_sidebar_fill_color": "EFEFEF",
        "profile_text_color": "333333",
        "screen_name": "imeoin",
        "statuses_count": 278,
        "url": "http://t.co/p9hKpiGMyN"
    },
    "user_mentions": [
        {
            "id": 783214,
            "name": "Twitter",
            "screen_name": "Twitter"
        },
        {
            "id": 14792670,
            "name": "Bosco So",
            "screen_name": "boscomonkey"
        },
        {
            "id": 819797,
            "name": "Taylor Singletary",
            "screen_name": "episod"
        }
    ]
}"""

def twitter(tweet_id: str) -> Optional[Dict[str, Any]]:
    if tweet_id in ["112652479837110273", "287977969287315456", "287977969287315457"]:
        return ujson.loads(NORMAL_TWEET)
    elif tweet_id == "287977969287315458":
        return ujson.loads(MENTION_IN_LINK_TWEET)
    elif tweet_id == "287977969287315459":
        return ujson.loads(MEDIA_TWEET)
    elif tweet_id == "287977969287315460":
        return ujson.loads(EMOJI_TWEET)
    else:
        return None

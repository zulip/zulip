from zerver.lib.hotspots import get_next_hotspots
from zerver.models import UserHotspot, UserProfile
from zerver.tornado.django_api import send_event


def do_mark_hotspot_as_read(user: UserProfile, hotspot: str) -> None:
    UserHotspot.objects.get_or_create(user=user, hotspot=hotspot)
    event = dict(type="hotspots", hotspots=get_next_hotspots(user))
    send_event(user.realm, event, [user.id])

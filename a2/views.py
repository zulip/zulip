
@zulip_internal
@has_request_variables
def get_activity(request):
    # type: (HttpRequest) -> HttpResponse
    duration_content, realm_minutes = user_activity_intervals() # type: Tuple[mark_safe, Dict[str, float]]
    counts_content = realm_summary_table(realm_minutes) # type: str
    data = [
        ('Counts', counts_content),
        ('Durations', duration_content),
    ]
    for page in ad_hoc_queries():
        data.append((page['title'], page['content']))

    title = 'Activity'

    return render_to_response(
        'analytics/activity.html',
        dict(data=data, title=title, is_home=True),
        request=request
    )

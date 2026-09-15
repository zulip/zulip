def meets_communities_directory_base_criteria(
    *,
    description: str,
    invite_required: bool,
    emails_restricted_to_domains: bool,
    has_web_public_streams: bool,
    is_demo_organization: bool,
) -> bool:
    """The criteria an organization asking to be advertised in the
    communities directory must meet.

    These are all the required criteria for cloud orgs; a remote
    organization must additionally be reachable.
    """
    if description == "":
        # Organizations that never wrote a description.
        return False

    if is_demo_organization:
        return False

    open_to_public = not invite_required and not emails_restricted_to_domains
    return has_web_public_streams or open_to_public

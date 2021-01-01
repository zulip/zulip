!!! warn ""
    This endpoint is limited to organizations administrators who
    additionally have the `can_create_users` permission for the Zulip organization.

    Zulip Cloud users can request the `can_create_users` permission for a bot by contacting
    [Zulip Cloud support](/help/contact-support) with an explanation for why it is needed.

    Self-hosted installations can toggle `can_create_users` on an account using
    the `manage.py change_user_role` command.

    **Changes**: Before Zulip 4.0 (feature level 36), this endpoint was
    available to all organization administrators.

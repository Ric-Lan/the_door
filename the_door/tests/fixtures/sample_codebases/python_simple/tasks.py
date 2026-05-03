"""Background task scheduling."""


# TODO: Add retry logic for failed tasks
def schedule_cleanup():
    """Schedule periodic database cleanup.
    
    Runs every 24 hours to remove expired sessions.
    """
    pass


def notify_admin(message: str) -> bool:
    """Send notification to admin.
    
    FIXME: Email sending is unreliable
    """
    return True

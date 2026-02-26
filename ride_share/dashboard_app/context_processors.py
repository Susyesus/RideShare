from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        # Get unread count and latest 5 notifications
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        latest_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:5]

        return {
            'unread_notification_count': unread_count,
            'user_notifications': latest_notifications
        }
    return {}

def user_profile_picture(request):
    """Add user's profile picture to all templates."""
    if request.user.is_authenticated:
        return {
            'user_picture': request.session.get('user_picture')
        }
    return {}
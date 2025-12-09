from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

from .models import Notification
from ride_app.models import Ride
from ride_app.models import Booking

@never_cache
@login_required
def dashboard(request):
    upcoming_rides = Ride.objects.filter(status='open').order_by('start_date', 'start_time')
    rides_count = upcoming_rides.count()
    kpis = {
        "completed_bookings_count": Booking.objects.filter(
            passenger=request.user, 
            status='completed'
        ).count()
    }
    context = {
        "kpis": kpis,
        "upcoming_rides": upcoming_rides,
        "rides_count": rides_count,
    }
    return render(request, "dashboard_app/dashboard.html", context)

@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user).update(is_read=True)
    return redirect('dashboard')

@login_required
def read_notification(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id)
    if notif.user == request.user:
        notif.is_read = True
        notif.save()
        # Redirect to the link stored in the notification (e.g., My Rides)
        return redirect(notif.link if notif.link else 'dashboard')
    return redirect('dashboard')

@login_required
def logout_view(request):
    """Handle user logout and redirect to landing page"""
    print(f"Logout view called by user: {request.user}")
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    print("User logged out, redirecting to landing page")
    return redirect('landing')

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from datetime import datetime

from .forms import PostRideForm, BookRideForm
from .models import Ride, Booking
from profile_app.supabase_utils import get_supabase_client
from dashboard_app.models import Notification

# Create your views here.

@login_required
def post_ride(request):
    """Render the post ride page"""

    # Prevent posting if user already has a booking
    active_booking = Booking.objects.filter(
        passenger=request.user,
        status__in=['confirmed', 'pending']
    ).first()

    if active_booking:
        messages.error(
            request,
            "You cannot post a ride while you have an active booking. "
            "Please cancel or complete your booking first."
        )
        return redirect('my_bookings')

    if request.method == 'POST':
        form = PostRideForm(request.POST)
        if form.is_valid():
            ride = form.save(commit=False)
            ride.driver = request.user
            ride.status = 'open'
            ride.save()
            return redirect('my_rides')
    else:
        form = PostRideForm()

    return render(request, "dashboard_app/post_ride.html", {'form': form})


@login_required
def find_rides(request):
    """Render the find rides page"""
    rides = Ride.objects.filter(status='open').order_by('start_date', 'start_time')
    # Initialize Supabase client
    supabase = get_supabase_client()

    # Fetch profile_picture_url for each driver
    driver_ids = [ride.driver.id for ride in rides]
    response = supabase.table('profiles').select('user_id, profile_picture_url').in_('user_id', driver_ids).execute()
    driver_profiles = {p['user_id']: p['profile_picture_url'] for p in response.data} if response.data else {}

    # Attach profile URL to each ride object for template
    for ride in rides:
        ride.driver_pic = driver_profiles.get(str(ride.driver.id))

    # Optional filter
    origin = request.GET.get('origin')
    destination = request.GET.get('destination')
    date = request.GET.get('date')

    #For ride matching
    if origin:
        rides = rides.filter(origin__icontains=origin)
    if destination:
        rides = rides.filter(destination__icontains=destination)
    if date:
        rides = rides.filter(start_date=date)
    return render(request, "dashboard_app/find_rides.html", {'rides':rides})


@login_required
def book_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)
    
    if request.method == 'POST':
        form = BookRideForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.ride = ride
            booking.passenger = request.user
            booking.status = 'pending' 
            booking.save()

            Notification.objects.create(
                user=ride.driver,
                message=f"{request.user.first_name} requested {booking.num_seats} seat(s) for {ride.destination}.",
                link="/ride/my-rides/"
            )

            messages.success(request, "Booking request sent!")
            return redirect('my_bookings')
    else:
        form = BookRideForm()

    return render(request, 'dashboard_app/book_ride.html', {'ride': ride, 'form': form})

@login_required
def accept_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    ride = booking.ride

    # US 4.2: Security check - only the driver can accept
    if request.user != ride.driver:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect('my_rides')

    # Update Logic
    if ride.seats_available >= booking.num_seats:
        booking.status = 'confirmed'
        booking.save()
        
        # Decrement seats only upon confirmation
        ride.seats_available -= booking.num_seats
        if ride.seats_available == 0:
            ride.status = 'full'
        ride.save()

        # US 4.1: Notify passenger when booking is confirmed
        Notification.objects.create(
            user=booking.passenger,
            message=f"Your ride to {ride.destination} has been confirmed!",
            link="/ride/my-bookings/"
        )
        
        messages.success(request, f"Confirmed booking for {booking.passenger.first_name}")
    else:
        messages.error(request, "Not enough seats available to confirm this booking.")

    return redirect('my_rides')

@login_required
def decline_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    if request.user != booking.ride.driver:
        messages.error(request, "You are not authorized.")
        return redirect('my_rides')

    booking.status = 'declined'
    booking.save()

    Notification.objects.create(
        user=booking.passenger,
        message=f"Your booking request to {booking.ride.destination} was declined.",
        link="/ride/find/"
    )

    messages.info(request, "Booking request declined.")
    return redirect('my_rides')

@login_required
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)

    if request.user == ride.driver:
        ride.status = 'completed'
        ride.save()
        messages.success(request, "Ride marked as completed.")
    
    return redirect('my_rides')

@login_required
def my_bookings(request):
    """Show user's bookings"""
    bookings = Booking.objects.filter(passenger=request.user).order_by('-created_at')
    return render(request, "dashboard_app/my_bookings.html", {'bookings': bookings})

@login_required
def my_rides(request):
    """Show user's posted rides"""
    rides = Ride.objects.filter(driver=request.user).order_by('-start_date', '-start_time')
    return render(request, "dashboard_app/my_rides.html", {'rides': rides})

@login_required
def close_ride(request, ride_id):
    """Close a posted ride and mark all bookings as closed"""
    ride = get_object_or_404(Ride, id=ride_id)

    # Check if user is the ride owner
    if ride.driver != request.user:
        messages.error(request, "You can only close your own rides.")
        return redirect('find_rides')

    # Close the ride
    ride.status = 'closed'
    ride.save()

    # Mark all bookings as closed
    Booking.objects.filter(ride=ride).update(status='closed')

    messages.success(request, "Ride closed successfully! All bookings have been marked as closed.")
    return redirect('my_rides')

@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, passenger=request.user)
    ride = booking.ride

    # 1. Time Check Logic
    ride_datetime = datetime.combine(ride.start_date, ride.start_time)
    if timezone.is_aware(timezone.now()):
        ride_datetime = timezone.make_aware(ride_datetime)

    if ride_datetime < timezone.now():
        messages.error(request, "You cannot cancel a ride that has already started.")
        return redirect('my_bookings')

    # 2. Seat Return Logic
    # Only return the seat if the booking was actually Confirmed (taking up space)
    if booking.status == 'confirmed':
        ride.seats_available += booking.num_seats
        # If ride was full, reopen it
        if ride.status == 'full':
            ride.status = 'open'
        ride.save()

    # 3. Update Status
    booking.status = 'cancelled'
    booking.save()

    # 4. Notify Driver (US 4.1 Requirement)
    Notification.objects.create(
        user=ride.driver,
        message=f"{request.user.first_name} cancelled their booking for {ride.destination}.",
        link="/ride/my-rides/"
    )

    messages.success(request, "Your booking has been cancelled successfully.")
    return redirect('my_bookings')
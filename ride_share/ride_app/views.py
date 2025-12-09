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

from dashboard_app.utils import attach_driver_profile_pictures
from dashboard_app.models import Notification

# Create your views here.

@login_required
def post_ride(request):
    """Render the post ride page"""

    # Prevent posting if user already has a booking
    active_booking = Booking.objects.filter(
        passenger=request.user,
        status__in=['accepted', 'pending','ongoing'],
        ride__status__in=['open', 'full']
    ).first()

    # Prevent posting if user already has a ride posted
    active_ride = Ride.objects.filter(
        driver=request.user, 
        status__in=['open', 'full', 'ongoing']
    ).exists()
    
    if active_ride:
        messages.error(request, "You already have an active ride. Please complete or close it first.")
        return redirect('my_rides')

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
            messages.success(request, "You have succefully posted a ride.")
            return redirect('my_rides')
    else:
        form = PostRideForm()

    return render(request, "dashboard_app/post_ride.html", {'form': form})


@login_required
def find_rides(request):
    """Render the find rides page"""
    rides = Ride.objects.filter(status='open').order_by('start_date', 'start_time')

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

    rides = attach_driver_profile_pictures(rides)
    return render(request, "dashboard_app/find_rides.html", {'rides':rides})


@login_required
def book_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)

    # Prevent posting if user already has a booking
    active_booking = Booking.objects.filter(
        passenger=request.user,
        status__in=['accepted', 'pending','ongoing'],
        ride__status__in=['open', 'full']
    ).first()

    # Prevent posting if user already has a ride posted
    active_ride = Ride.objects.filter(
        driver=request.user, 
        status__in=['open', 'full', 'ongoing']
    ).exists()
    
    if active_ride:
        messages.error(request, "You already have an active ride. Please complete or close it first.")
        return redirect('my_rides')

    if active_booking:
        messages.error(
            request,
            "You cannot post a ride while you have an active booking. "
            "Please cancel or complete your booking first."
        )
        return redirect('my_bookings')
    
    if request.method == 'POST':
        form = BookRideForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)

            seats_available = ride.seats_available
            if booking.num_seats > seats_available:
                messages.error(request, f"Cannot book {booking.num_seats} seats. Only {seats_available} seats available.")
                # Return the user to the form with the data they entered
                return render(request, 'dashboard_app/book_ride.html', {'ride': ride, 'form': form})

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

    # Security check - only the driver can accept
    if request.user != ride.driver:
        messages.error(request, "You are not authorized to perform this action.")
        return redirect('my_rides')

    # Update Logic
    if ride.seats_available >= booking.num_seats:
        booking.status = 'accepted'
        booking.save()
        
        # Decrement seats only upon confirmation
        ride.seats_available -= booking.num_seats
        
        # Check if ride is now full
        if ride.seats_available == 0:
            ride.status = 'full'
            
            # === NEW LOGIC: Auto-decline pending requests ===
            pending_bookings = ride.bookings.filter(status='pending')
            
            # Notify them
            for pb in pending_bookings:
                Notification.objects.create(
                    user=pb.passenger,
                    message=f"The ride to {ride.destination} is now full. Your pending request was automatically declined.",
                    link="/ride/my-bookings/"
                )
            
            # Bulk update status
            pending_bookings.update(status='declined')
            # ================================================

        ride.save()

        # Notify the accepted passenger
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
        link="/ride/my-bookings/"
    )

    messages.info(request, "Booking request declined.")
    return redirect('my_rides')

@login_required
def complete_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)

    ride_datetime = datetime.combine(ride.start_date, ride.start_time)
    if timezone.is_aware(timezone.now()):
        ride_datetime = timezone.make_aware(ride_datetime)

    if timezone.now() < ride_datetime:
        messages.error(request, "You cannot complete a ride that hasn't started yet.")
        return redirect('my_rides')

    if request.user == ride.driver:
        ride.status = 'completed'
        ride.save()
        
         # Get bookings BEFORE updating
        ongoing_bookings = list(ride.bookings.filter(status='ongoing'))

        # Update booking statuses
        ride.bookings.filter(status='ongoing').update(status='completed')

        # Notify each passenger
        for booking in ongoing_bookings:
            Notification.objects.create(
                user=booking.passenger,
                message=f"Your ride to {ride.destination} has been completed!",
                link="/ride/my-bookings/"
            )

    
    messages.success(request, "Ride marked as completed.")
    return redirect('my_rides')

@login_required
def my_bookings(request):
    """Show user's bookings"""
    bookings = Booking.objects.filter(passenger=request.user)\
        .select_related('ride', 'ride__driver')\
        .order_by('-id')
    return render(request, "dashboard_app/my_bookings.html", {'bookings': bookings})

@login_required
def my_rides(request):
    """Show user's posted rides and reviews received from passengers"""
    
    # 1. Fetch the Driver's Rides
    rides = Ride.objects.filter(driver=request.user).order_by('-id')

    # 2. Fetch the Reviews (Bookings that have a rating)
    # We filter by 'ride__driver' to get ratings for this user
    reviews = Booking.objects.filter(
        ride__driver=request.user,
        rating_stars__isnull=False
    ).select_related('passenger', 'ride').order_by('-rated_at')

    # 3. Add both to context
    context = {
        'rides': rides,
        'reviews': reviews
    }
    
    return render(request, "dashboard_app/my_rides.html", context)

@login_required
def cancel_ride(request, ride_id):
    """Cancel a posted ride, notify passengers, and mark bookings as cancelled"""
    ride = get_object_or_404(Ride, id=ride_id)

    # Check if user is the ride owner
    if ride.driver != request.user:
        messages.error(request, "You can only cancel your own rides.")
        return redirect('my_rides')

    # 1. Update Ride Status
    ride.status = 'cancelled'
    ride.save()

    # 2. Get affected bookings BEFORE updating them (to know who to notify)
    affected_bookings = ride.bookings.filter(status__in=['pending', 'accepted'])

    # 3. Create Notifications
    for booking in affected_bookings:
        Notification.objects.create(
            user=booking.passenger,
            message=f"The ride to {ride.destination} was cancelled by the driver.",
            link="/ride/my-bookings/"
        )

    # 4. Mark all bookings as cancelled
    affected_bookings.update(status='cancelled')

    messages.success(request, "Ride cancelled successfully! Passengers have been notified.")
    return redirect('my_rides')

@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, passenger=request.user)
    ride = booking.ride

    # 1. Check if already accepted
    if booking.status == 'accepted':
        messages.error(request, "You cannot cancel a booking that has already been accepted by the driver.")
        return redirect('my_bookings')

    # 2. Time Check Logic
    # ride_datetime = datetime.combine(ride.start_date, ride.start_time)
    # if timezone.is_aware(timezone.now()):
    #     ride_datetime = timezone.make_aware(ride_datetime)

    # if ride_datetime < timezone.now():
    #     messages.error(request, "You cannot cancel a ride that has already started.")
    #     return redirect('my_bookings')

    # 3. Update Status (Only for pending bookings now)
    booking.status = 'cancelled'
    booking.save()

    # 4. Notify Driver
    Notification.objects.create(
        user=ride.driver,
        message=f"{request.user.first_name} cancelled their pending request for {ride.destination}.",
        link="/ride/my-rides/"
    )

    messages.success(request, "Your booking request has been cancelled.")
    return redirect('my_bookings')

@login_required
def submit_booking_rating(request):
    if request.method == "POST":
        booking_id = request.POST.get("booking_id")
        stars = int(request.POST.get("stars", 0))
        review = request.POST.get("review", "").strip()

        booking = get_object_or_404(
            Booking, id=booking_id, passenger=request.user, status__in=['completed', 'closed']
        )

        if booking.rating_stars:
            messages.info(request, "You have already rated this driver.")
            return redirect('my_bookings')

        if stars < 1 or stars > 5:
            messages.error(request, "Stars must be between 1 and 5.")
            return redirect('my_bookings')

        booking.rating_stars = stars
        booking.rating_review = review
        booking.rated_at = timezone.now()
        booking.save()

        messages.success(request, "Driver rated successfully!")
    return redirect('my_bookings')

@login_required
def start_ride(request, ride_id):
    ride = get_object_or_404(Ride, id=ride_id)

    # Only the driver can start the ride
    if ride.driver != request.user:
        messages.error(request, "You can only start your own rides.")
        return redirect('my_rides')

    # Prevent starting before scheduled time
    ride_datetime = datetime.combine(ride.start_date, ride.start_time)
    if timezone.is_naive(ride_datetime):
        ride_datetime = timezone.make_aware(ride_datetime)

    if timezone.now() < ride_datetime:
        messages.error(request, "You cannot start the ride before its scheduled time.")
        return redirect('my_rides')

    # Only allow starting if ride is open or full
    if ride.status not in ['open', 'full']:
        messages.error(request, f"Cannot start a ride with status '{ride.status}'.")
        return redirect('my_rides')

    # Update ride status
    ride.status = 'ongoing'
    ride.save()

    # Update all accepted bookings to 'ongoing' and notify passengers
    accepted_bookings = ride.bookings.filter(status='accepted')
    for booking in accepted_bookings:
        booking.status = 'ongoing'
        booking.save()

        # Send notification
        Notification.objects.create(
            user=booking.passenger,
            message=f"Your ride from {ride.origin} to {ride.destination} has started!",
            link="/ride/my-bookings/"
        )

    # 2. NEW: Auto-decline pending bookings
    pending_bookings = ride.bookings.filter(status='pending')
    for booking in pending_bookings:
        booking.status = 'declined'  # Ensure this matches your models choices
        booking.save()

        # Notify passenger
        Notification.objects.create(
            user=booking.passenger,
            message=f"Your booking request for {ride.origin} to {ride.destination} was automatically declined because the ride has started.",
            link="/ride/my-bookings/"
        )

    messages.success(request, "Ride started successfully. Passengers have been notified.")
    return redirect('my_rides')
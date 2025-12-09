from django import forms
from .models import Ride, Booking
from datetime import date
from django.utils import timezone
from datetime import datetime, date

class PostRideForm(forms.ModelForm):
    class Meta:
        model = Ride
        fields = ['origin', 'destination', 'seats_available', 'start_date', 'start_time', 'price', 'remarks']
        widgets = {
            'seats_available': forms.NumberInput(attrs={'type': 'number','min': '1','step': '1'}),
            'start_date': forms.DateInput(attrs={'type': 'date',  'min': date.today().strftime('%Y-%m-%d'),'id': 'rideDate', }),
            'start_time': forms.TimeInput(attrs={'type': 'time','id': 'rideTime',}),
            'price': forms.NumberInput(attrs={'type': 'number','min': '0.00','step': '0.01'}), # allow decimals
            'remarks': forms.Textarea( attrs={'rows': 3,'placeholder': 'Optional remarks about your ride...'}),
        }

        def clean(self):
            # 1. Get the data cleaned by default validations first
            cleaned_data = super().clean()
            start_date = cleaned_data.get('start_date')
            start_time = cleaned_data.get('start_time')

            # 2. Ensure both fields were provided
            if start_date and start_time:
                # Get current date and time
                now = datetime.now() 
                today = now.date()
                current_time = now.time()

                # 3. Check: Is the date in the past?
                if start_date < today:
                    self.add_error('start_date', "You cannot post a ride for a past date.")

                # 4. Check: Is the date today, but the time in the past?
                elif start_date == today:
                    if start_time < current_time:
                        self.add_error('start_time', "The time has already passed.")

            return cleaned_data



class BookRideForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['num_seats']
        widgets = {
            'num_seats': forms.NumberInput(attrs={'type': 'number', 'min': 1, 'max': 6})
        }
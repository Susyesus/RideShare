from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from .forms import UserLoginForm

def login(request):
    error = None
    form = UserLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']

        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                auth_login(request, user)

                # Redirect admins to /admin
                if user.is_staff or user.is_superuser:
                    return redirect('/admin')
                    
                return redirect('dashboard')
            else:
                error = "Invalid email or password."
        except User.DoesNotExist:
            error = "Invalid email or password."

    return render(request, "login_app/login.html", {"form": form, "error": error})

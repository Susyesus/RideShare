from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from .forms import UserLoginForm
from dashboard_app.utils import get_user_profile_picture

def login(request):
    error = None
    form = UserLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']

        try:
            print("DEBUG 1: Looking up user in DB...", flush=True)
            user_obj = User.objects.get(email=email)
            
            print("DEBUG 2: Authenticating user...", flush=True)
            user = authenticate(request, username=user_obj.username, password=password)
            
            if user is not None:
                print("DEBUG 3: Logging in user...", flush=True)
                auth_login(request, user)
                
                print("DEBUG 4: Fetching profile picture from Supabase...", flush=True)
                profile_pic = get_user_profile_picture(user)
                
                print(f"DEBUG 5: Picture fetched: {profile_pic != None}. Saving to session...", flush=True)
                if profile_pic:
                    request.session['user_picture'] = profile_pic

                print("DEBUG 6: Redirecting...", flush=True)
                if user.is_staff or user.is_superuser:
                    return redirect('/admin')
                    
                return redirect('dashboard')
            else:
                error = "Invalid email or password."
        except User.DoesNotExist:
            error = "Invalid email or password."
        except Exception as e:
            print(f"DEBUG ERROR: An exception occurred: {str(e)}", flush=True)
            error = "An error occurred during login."

    return render(request, "login_app/login.html", {"form": form, "error": error})

# from django.shortcuts import render, redirect
# from django.contrib.auth import authenticate, login as auth_login
# from django.contrib.auth.models import User
# from .forms import UserLoginForm
# from dashboard_app.utils import get_user_profile_picture

# def login(request):
#     error = None
#     form = UserLoginForm(request.POST or None)

#     if request.method == "POST" and form.is_valid():
#         email = form.cleaned_data['email']
#         password = form.cleaned_data['password']

#         try:
#             user_obj = User.objects.get(email=email)
#             user = authenticate(request, username=user_obj.username, password=password)
#             if user is not None:
#                 auth_login(request, user)
                
#                 # Fetch the picture ONCE during login and save it to the session
#                 profile_pic = get_user_profile_picture(user)
#                 if profile_pic:
#                     request.session['user_picture'] = profile_pic

#                 # Redirect admins to /admin
#                 if user.is_staff or user.is_superuser:
#                     return redirect('/admin')
                    
#                 return redirect('dashboard')
#             else:
#                 error = "Invalid email or password."
#         except User.DoesNotExist:
#             error = "Invalid email or password."

#     return render(request, "login_app/login.html", {"form": form, "error": error})

import os
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.conf import settings
from register_app.models import EmailVerificationToken
from django.contrib.auth.models import User
from django.http import HttpResponse
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from register_app.models import EmailVerificationToken

def send_verification_email(user):
    # Create or get a token
    token_obj, created = EmailVerificationToken.objects.get_or_create(user=user)
    site_url = os.getenv("SITE_URL", "http://127.0.0.1:8000")
    verification_link = f"{site_url}/accounts/verify/{token_obj.token}/"

    # Email content
    subject = "Verify your email"

    html_content = f"""
<p>Hi {user.first_name} {user.last_name},</p>
<p>Please verify your email by clicking this link:</p>
<p><a href="{verification_link}">{verification_link}</a></p>
<p>Thank you!</p>
    """

    # Must match your verified sender in SendGrid
    from_email = "auditormechole@gmail.com"
    to_email = user.email

    message = f"Hi {user.first_name} {user.last_name},\n\nPlease verify your email by clicking this link:\n{verification_link}\n\nThank you!"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]


    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)
        print(f"✅ Email sent! Status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


def verify_email(request, token):
    try:
        token_obj = EmailVerificationToken.objects.get(token=token)
    except EmailVerificationToken.DoesNotExist:
        return HttpResponse("❌ Invalid or broken verification link.")

    if token_obj.is_valid():
        user = token_obj.user
        user.is_active = True
        user.save()
        token_obj.delete()
        return redirect('login')
    else:
        return HttpResponse("⚠️ Link expired. Please register again.")


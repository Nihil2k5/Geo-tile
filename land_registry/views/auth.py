from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.utils.crypto import get_random_string
from django.utils import timezone

from land_registry.models import User
from land_registry.blockchain.wallet import WalletManager

def register(request):
    """
    Handle user registration with email verification.
    """
    if request.user.is_authenticated:
        return redirect('land_registry:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        role = request.POST.get('role')

        if not all([username, email, first_name, last_name, password, role]):
            messages.error(request, 'All fields are required.')
            return render(request, 'auth/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'auth/register.html')

        try:
            with transaction.atomic():
                # Create a new wallet for the user
                wallet_manager = WalletManager()
                wallet = wallet_manager.create_wallet()

                # Generate verification token
                verification_token = get_random_string(64)

                # Create user in database with wallet address
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role=role,
                    wallet_address=wallet.address,
                    is_active=False,  # User starts inactive until email is verified
                    verification_token=verification_token
                )

                # Send verification email
                verification_url = f"{request.scheme}://{request.get_host()}/verify-email/{verification_token}/"
                send_mail(
                    'Verify your GeoLedger account',
                    f'Click this link to verify your email: {verification_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )

                messages.success(request, 'Registration successful! Please check your email to verify your account.')
                return redirect('land_registry:login')

        except Exception as e:
            messages.error(request, f'Error during registration: {str(e)}')

    return render(request, 'auth/register.html')

def login_view(request):
    """
    Handle user login.
    """
    if request.user.is_authenticated:
        return redirect('land_registry:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'Please verify your email before logging in.')
                return render(request, 'auth/login.html')
            
            login(request, user)
            return redirect('land_registry:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'auth/login.html')

def verify_email(request, token):
    """
    Handle email verification.
    """
    try:
        user = User.objects.get(verification_token=token, is_active=False)
        user.is_active = True
        user.email_verified_at = timezone.now()
        user.verification_token = None
        user.save()
        messages.success(request, 'Email verified successfully! You can now log in.')
        return redirect('land_registry:login')
    except User.DoesNotExist:
        messages.error(request, 'Invalid verification token.')
        return redirect('land_registry:login')

@login_required
def dashboard(request):
    """
    Redirect to role-specific dashboard.
    """
    role = request.user.role
    if role == 'admin':
        return redirect('land_registry:admin_dashboard')
    elif role == 'registrar':
        return redirect('land_registry:registrar_dashboard')
    elif role == 'surveyor':
        return redirect('land_registry:surveyor_dashboard')
    elif role == 'citizen':
        return redirect('land_registry:citizen_dashboard')
    elif role == 'court':
        return redirect('land_registry:court_dashboard')
    else:
        messages.error(request, 'Invalid user role.')
        return redirect('land_registry:login')
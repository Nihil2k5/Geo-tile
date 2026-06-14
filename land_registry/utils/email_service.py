"""
Email service for sending land registry notifications
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
import logging
import qrcode
import base64
import json
from io import BytesIO

logger = logging.getLogger(__name__)

def generate_parcel_qr_code_base64(parcel):
    """
    Generate QR code for a parcel and return as base64 string.
    
    Args:
        parcel: Parcel instance
        
    Returns:
        base64-encoded QR code image string, or None if generation fails
    """
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        # Prepare QR code data with parcel details
        qr_data = {
            'id': str(parcel.id),
            'location': parcel.location or 'No location',
            'area': parcel.area,
            'owner': parcel.owner.get_full_name(),
            'owner_wallet': parcel.owner.wallet_address or 'Not assigned',
            'status': parcel.status,
            'blockchain_tx': parcel.blockchain_tx_hash or 'pending',
            'registration_date': parcel.created_at.isoformat() if parcel.created_at else None
        }
        
        # Convert to JSON string and add to QR code
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Create QR code image
        qr_image = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 string
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        qr_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return qr_image_base64
    except Exception as e:
        logger.error(f"Error generating parcel QR code: {str(e)}", exc_info=True)
        return None

def send_land_registration_email(parcel, owner):
    """
    Send email notification to the owner when their land is registered.
    
    Args:
        parcel: Parcel instance that was registered
        owner: User instance (owner of the parcel)
    """
    try:
        if not owner.email:
            logger.warning(f"Owner {owner.username} does not have an email address, skipping email notification")
            return False
        
        # Get current site for URL generation
        try:
            from django.contrib.sites.models import Site
            current_site = Site.objects.get_current()
            site_domain = current_site.domain
        except:
            site_domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'  # Fallback for development
        
        # Generate QR code for the parcel
        parcel_qr_code = generate_parcel_qr_code_base64(parcel)
        
        # Prepare email context
        context = {
            'owner': owner,
            'parcel': parcel,
            'parcel_id': parcel.id,
            'location': parcel.location,
            'area': parcel.area,
            'registration_date': parcel.created_at,
            'status': parcel.get_status_display(),
            'blockchain_tx_hash': parcel.blockchain_tx_hash,
            'registrar_name': parcel.original_registrar.get_full_name() if parcel.original_registrar else 'System',
            'site_domain': site_domain,
            'parcel_qr_code': parcel_qr_code,  # QR code as base64 image
        }
        
        # Render email template
        html_message = render_to_string('emails/land_registered.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=f'Land Registration Confirmation - Parcel #{parcel.id}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Land registration email sent successfully to {owner.email} for parcel #{parcel.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending land registration email: {str(e)}", exc_info=True)
        # Don't fail the registration if email fails
        return False

def send_land_verification_email(parcel, owner):
    """
    Send email notification to the owner when their land is verified.
    
    Args:
        parcel: Parcel instance that was verified
        owner: User instance (owner of the parcel)
    """
    try:
        if not owner.email:
            logger.warning(f"Owner {owner.username} does not have an email address, skipping email notification")
            return False
        
        # Get current site for URL generation
        try:
            from django.contrib.sites.models import Site
            current_site = Site.objects.get_current()
            site_domain = current_site.domain
        except:
            site_domain = settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'  # Fallback for development
        
        # Generate QR code for the parcel
        parcel_qr_code = generate_parcel_qr_code_base64(parcel)
        
        # Prepare email context
        context = {
            'owner': owner,
            'parcel': parcel,
            'parcel_id': parcel.id,
            'location': parcel.location,
            'area': parcel.area,
            'verification_date': parcel.updated_at,
            'status': parcel.get_status_display(),
            'blockchain_tx_hash': parcel.blockchain_tx_hash,
            'site_domain': site_domain,
            'parcel_qr_code': parcel_qr_code,  # QR code as base64 image
        }
        
        # Render email template
        html_message = render_to_string('emails/land_verified.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email
        send_mail(
            subject=f'Land Verification Confirmation - Parcel #{parcel.id}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Land verification email sent successfully to {owner.email} for parcel #{parcel.id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending land verification email: {str(e)}", exc_info=True)
        # Don't fail the verification if email fails
        return False

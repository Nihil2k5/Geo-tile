# Email Configuration Guide

This application sends email notifications when land parcels are registered and verified. This guide explains how to configure email settings.

## Current Configuration

The application is currently configured to use the **console email backend** for development, which prints emails to the console instead of actually sending them.

## For Development (Current Setup)

The emails are printed to the Django console/logs. No actual emails are sent. This is perfect for development and testing.

## For Production

To enable actual email sending in production, you need to configure SMTP settings:

### Option 1: Gmail SMTP (Recommended for Testing)

1. **Enable 2-Factor Authentication** on your Gmail account
2. **Generate an App Password**:
   - Go to Google Account Settings
   - Security → 2-Step Verification → App passwords
   - Generate a password for "Mail"
3. **Update `geoledger/settings.py`**:

```python
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'  # Use the app password, not your regular password
DEFAULT_FROM_EMAIL = 'your-email@gmail.com'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
```

### Option 2: Custom SMTP Server

```python
# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.yourdomain.com'
EMAIL_PORT = 587  # or 465 for SSL
EMAIL_USE_TLS = True  # Use False for SSL on port 465
EMAIL_HOST_USER = 'noreply@yourdomain.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'noreply@yourdomain.com'
SERVER_EMAIL = DEFAULT_FROM_EMAIL
```

### Option 3: Using Environment Variables (Recommended for Production)

For security, store sensitive email credentials in environment variables:

1. **Create a `.env` file** (or use your environment):
```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@gmail.com
```

2. **Update `settings.py`** to use environment variables:
```python
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@geoledger.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
```

## Email Templates

Email templates are located in:
- `land_registry/templates/emails/land_registered.html` - Sent when land is registered
- `land_registry/templates/emails/land_verified.html` - Sent when land is verified

You can customize these templates to match your branding.

## Email Features

The application currently sends emails for:

1. **Land Registration**: When a new land parcel is registered, the owner receives a confirmation email with parcel details.
2. **Land Verification**: When a land parcel is verified and activated, the owner receives a confirmation email.

## Testing Emails

### Console Backend (Development)
When using console backend, emails are printed to the Django console. Check your terminal/console output after registering or verifying land.

### SMTP Backend (Production)
1. Configure SMTP settings as shown above
2. Register or verify a land parcel
3. Check the owner's email inbox

## Troubleshooting

### Emails Not Sending

1. **Check Email Settings**: Verify EMAIL_BACKEND, EMAIL_HOST, EMAIL_PORT, etc. are correctly configured
2. **Check Credentials**: Verify EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are correct
3. **Check Firewall**: Ensure port 587 (or 465) is not blocked
4. **Check Logs**: Check Django logs for email-related errors
5. **Test Connection**: Try sending a test email using Django shell:
   ```python
   from django.core.mail import send_mail
   send_mail('Test', 'Test message', 'from@example.com', ['to@example.com'])
   ```

### Gmail Specific Issues

- Make sure 2-Factor Authentication is enabled
- Use App Password, not your regular password
- Check if "Less secure app access" is enabled (if not using App Passwords)

## Security Notes

- Never commit email passwords to version control
- Use environment variables for sensitive credentials
- Consider using dedicated email service (SendGrid, Mailgun, AWS SES) for production
- Use TLS/SSL for email connections in production

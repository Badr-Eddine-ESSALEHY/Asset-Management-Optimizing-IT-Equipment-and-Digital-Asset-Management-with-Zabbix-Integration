# assets/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Intervention
import logging

# Set up logging
logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=Intervention)
def send_intervention_notification(sender, instance, created, **kwargs):
    """
    Send email notification to all active admins when a new intervention is created.
    """
    if created:  # Only for new interventions, not updates
        try:
            # Get all active admin users (staff users with email addresses)
            admin_users = User.objects.filter(
                is_staff=True,
                is_active=True,
                email__isnull=False
            ).exclude(email='')

            if not admin_users.exists():
                logger.warning("No active admin users with email addresses found.")
                return

            admin_emails = [admin.email for admin in admin_users]

            # Prepare email content
            subject = f'New Intervention Created: {instance.title}'

            # Create the context for email templates
            context = {
                'intervention': instance,
                'technician': instance.technician,
                'equipment': instance.equipment,
                'site_url': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000'),
            }

            # FIXED: Correct template paths
            text_content = render_to_string('assets/emails/intervention_notification.txt', context)
            html_content = render_to_string('assets/emails/intervention_notification.html', context)

            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=admin_emails,
            )
            email.attach_alternative(html_content, "text/html")

            # Send the email
            email.send(fail_silently=False)

            # Log success
            logger.info(f"Intervention notification sent successfully for intervention ID: {instance.id}")
            logger.info(f"Email sent to: {', '.join(admin_emails)}")

        except Exception as e:
            # Log the error but don't raise it to avoid breaking the intervention creation
            logger.error(f"Failed to send intervention notification: {str(e)}")
            logger.error(f"Intervention ID: {instance.id}")


def send_intervention_status_update(intervention):
    """
    Helper function to send notifications when intervention status changes.
    Call this manually from views when needed.
    """
    try:
        admin_users = User.objects.filter(
            is_staff=True,
            is_active=True,
            email__isnull=False
        ).exclude(email='')

        if not admin_users.exists():
            logger.warning("No active admin users with email addresses found for status update.")
            return

        admin_emails = [admin.email for admin in admin_users]

        subject = f'Intervention Status Updated: {intervention.title}'

        context = {
            'intervention': intervention,
            'technician': intervention.technician,
            'equipment': intervention.equipment,
            'site_url': getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000'),
        }

        # FIXED: Correct template paths
        text_content = render_to_string('assets/emails/intervention_status_update.txt', context)
        html_content = render_to_string('assets/emails/intervention_status_update.html', context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=admin_emails,
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)

        logger.info(f"Status update notification sent for intervention ID: {intervention.id}")

    except Exception as e:
        logger.error(f"Failed to send status update notification: {str(e)}")
        raise  # Re-raise the exception so the view can handle it
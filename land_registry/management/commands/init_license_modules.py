"""
Management command to initialize license modules
"""
from django.core.management.base import BaseCommand
from land_registry.models import LicenseModule


class Command(BaseCommand):
    help = 'Initialize license modules (LandCore, LandVerify, LandAudit, LandExchange)'

    def handle(self, *args, **options):
        modules = [
            {
                'code': 'landcore',
                'name': 'LandCore',
                'description': 'Core land registry operations including registration, verification, and basic management.',
                'is_mandatory': True,
                'display_order': 1,
            },
            {
                'code': 'landverify',
                'name': 'LandVerify',
                'description': 'Advanced verification workflows for banks, field validation, and document verification.',
                'is_mandatory': False,
                'display_order': 2,
            },
            {
                'code': 'landaudit',
                'name': 'LandAudit',
                'description': 'Fraud detection indicators, dispute analytics, and comprehensive audit reporting.',
                'is_mandatory': False,
                'display_order': 3,
            },
            {
                'code': 'landexchange',
                'name': 'LandExchange',
                'description': 'Advanced transfer workflows, smart contract integration, and digital asset management.',
                'is_mandatory': False,
                'display_order': 4,
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for module_data in modules:
            module, created = LicenseModule.objects.update_or_create(
                code=module_data['code'],
                defaults={
                    'name': module_data['name'],
                    'description': module_data['description'],
                    'is_mandatory': module_data['is_mandatory'],
                    'display_order': module_data['display_order'],
                    'is_active': True,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created module: {module.name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated module: {module.name}'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nLicense modules initialized: {created_count} created, {updated_count} updated'
            )
        )

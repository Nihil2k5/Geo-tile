# Generated migration for comprehensive land parcel history tracking
from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('land_registry', '0012_parcel_is_legacy_parcel_legacy_document_and_more'),
    ]

    operations = [
        # Add original registration tracking fields to Parcel model
        migrations.AddField(
            model_name='parcel',
            name='original_owner',
            field=models.ForeignKey(
                null=True, 
                blank=True, 
                on_delete=models.PROTECT, 
                related_name='originally_owned_parcels',
                to=settings.AUTH_USER_MODEL,
                help_text="The first owner who registered this land parcel"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='original_surveyor',
            field=models.ForeignKey(
                null=True, 
                blank=True, 
                on_delete=models.SET_NULL, 
                related_name='originally_surveyed_parcels',
                to=settings.AUTH_USER_MODEL,
                limit_choices_to={'role': 'surveyor'},
                help_text="The surveyor who conducted the original survey"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='original_registration_date',
            field=models.DateTimeField(
                null=True, 
                blank=True,
                help_text="Date when this parcel was first registered in the system"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='original_area',
            field=models.FloatField(
                null=True, 
                blank=True,
                help_text="Original area as surveyed during first registration"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='original_coordinates',
            field=models.JSONField(
                null=True, 
                blank=True,
                help_text="Original GeoJSON coordinates from first survey"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='registration_number',
            field=models.CharField(
                max_length=50, 
                null=True, 
                blank=True, 
                unique=True,
                help_text="Unique registration number like traditional land records"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='survey_number',
            field=models.CharField(
                max_length=50, 
                null=True, 
                blank=True,
                help_text="Survey number from original land survey"
            ),
        ),
        migrations.AddField(
            model_name='parcel',
            name='village_tehsil',
            field=models.CharField(
                max_length=255, 
                null=True, 
                blank=True,
                help_text="Village and Tehsil information for traditional land records"
            ),
        ),

        # Create ParcelHistory model for tracking all changes
        migrations.CreateModel(
            name='ParcelHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('registration', 'Initial Registration'),
                        ('ownership_transfer', 'Ownership Transfer'),
                        ('survey_update', 'Survey Update'),
                        ('status_change', 'Status Change'),
                        ('document_update', 'Document Update'),
                        ('dispute_filed', 'Dispute Filed'),
                        ('dispute_resolved', 'Dispute Resolved'),
                    ],
                    help_text="Type of change made to the parcel"
                )),
                ('previous_value', models.JSONField(
                    null=True, 
                    blank=True,
                    help_text="Previous values before the change"
                )),
                ('new_value', models.JSONField(
                    null=True, 
                    blank=True,
                    help_text="New values after the change"
                )),
                ('change_reason', models.TextField(
                    null=True, 
                    blank=True,
                    help_text="Reason for the change"
                )),
                ('blockchain_tx_hash', models.CharField(
                    max_length=66, 
                    null=True, 
                    blank=True,
                    help_text="Blockchain transaction hash for this change"
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parcel', models.ForeignKey(
                    on_delete=models.CASCADE, 
                    related_name='history_records',
                    to='land_registry.parcel'
                )),
                ('changed_by', models.ForeignKey(
                    on_delete=models.PROTECT, 
                    related_name='parcel_changes_made',
                    to=settings.AUTH_USER_MODEL,
                    help_text="User who made this change"
                )),
                ('related_transaction', models.ForeignKey(
                    null=True, 
                    blank=True,
                    on_delete=models.SET_NULL, 
                    related_name='history_records',
                    to='land_registry.transaction'
                )),
            ],
            options={
                'verbose_name': 'Parcel History Record',
                'verbose_name_plural': 'Parcel History Records',
                'ordering': ['-created_at'],
            },
        ),

        # Create OwnershipChain model for tracking complete ownership history
        migrations.CreateModel(
            name='OwnershipChain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sequence_number', models.PositiveIntegerField(
                    help_text="Sequential number in the ownership chain (1 for original owner)"
                )),
                ('ownership_start_date', models.DateTimeField(
                    help_text="Date when this owner acquired the property"
                )),
                ('ownership_end_date', models.DateTimeField(
                    null=True, 
                    blank=True,
                    help_text="Date when this owner transferred the property (null for current owner)"
                )),
                ('transfer_method', models.CharField(
                    max_length=20,
                    choices=[
                        ('registration', 'Initial Registration'),
                        ('sale', 'Sale'),
                        ('inheritance', 'Inheritance'),
                        ('gift', 'Gift'),
                        ('court_order', 'Court Order'),
                        ('government_allocation', 'Government Allocation'),
                    ],
                    default='sale',
                    help_text="Method by which ownership was acquired"
                )),
                ('transfer_document', models.FileField(
                    upload_to='ownership_documents/', 
                    null=True, 
                    blank=True,
                    help_text="Document supporting the ownership transfer"
                )),
                ('blockchain_tx_hash', models.CharField(
                    max_length=66, 
                    null=True, 
                    blank=True,
                    help_text="Blockchain transaction hash for this ownership change"
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parcel', models.ForeignKey(
                    on_delete=models.CASCADE, 
                    related_name='ownership_chain',
                    to='land_registry.parcel'
                )),
                ('owner', models.ForeignKey(
                    on_delete=models.PROTECT, 
                    related_name='ownership_history',
                    to=settings.AUTH_USER_MODEL
                )),
                ('previous_owner', models.ForeignKey(
                    null=True, 
                    blank=True,
                    on_delete=models.PROTECT, 
                    related_name='properties_transferred_from',
                    to=settings.AUTH_USER_MODEL,
                    help_text="Previous owner (null for original registration)"
                )),
                ('related_transaction', models.ForeignKey(
                    null=True, 
                    blank=True,
                    on_delete=models.SET_NULL, 
                    related_name='ownership_records',
                    to='land_registry.transaction'
                )),
            ],
            options={
                'verbose_name': 'Ownership Chain Record',
                'verbose_name_plural': 'Ownership Chain Records',
                'ordering': ['parcel', 'sequence_number'],
                'unique_together': [['parcel', 'sequence_number']],
            },
        ),

        # Create SurveyHistory model for tracking all survey changes
        migrations.CreateModel(
            name='SurveyHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('survey_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('original', 'Original Survey'),
                        ('resurvey', 'Re-survey'),
                        ('boundary_correction', 'Boundary Correction'),
                        ('subdivision', 'Subdivision'),
                        ('consolidation', 'Consolidation'),
                    ],
                    help_text="Type of survey conducted"
                )),
                ('coordinates', models.JSONField(
                    help_text="GeoJSON coordinates from this survey"
                )),
                ('area', models.FloatField(
                    help_text="Area measured in this survey (square meters)"
                )),
                ('survey_notes', models.TextField(
                    null=True, 
                    blank=True,
                    help_text="Notes and observations from the surveyor"
                )),
                ('survey_documents', models.FileField(
                    upload_to='survey_documents/', 
                    null=True, 
                    blank=True,
                    help_text="Survey maps, reports, and related documents"
                )),
                ('blockchain_tx_hash', models.CharField(
                    max_length=66, 
                    null=True, 
                    blank=True,
                    help_text="Blockchain transaction hash for this survey update"
                )),
                ('survey_date', models.DateTimeField(
                    help_text="Date when the survey was conducted"
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parcel', models.ForeignKey(
                    on_delete=models.CASCADE, 
                    related_name='survey_history',
                    to='land_registry.parcel'
                )),
                ('surveyor', models.ForeignKey(
                    on_delete=models.PROTECT, 
                    related_name='conducted_surveys',
                    to=settings.AUTH_USER_MODEL,
                    limit_choices_to={'role': 'surveyor'}
                )),
            ],
            options={
                'verbose_name': 'Survey History Record',
                'verbose_name_plural': 'Survey History Records',
                'ordering': ['-survey_date'],
            },
        ),

        # Add indexes for better query performance
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_parcel_history_parcel_date ON land_registry_parcelhistory(parcel_id, created_at DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_parcel_history_parcel_date;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_ownership_chain_parcel_seq ON land_registry_ownershipchain(parcel_id, sequence_number);",
            reverse_sql="DROP INDEX IF EXISTS idx_ownership_chain_parcel_seq;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_survey_history_parcel_date ON land_registry_surveyhistory(parcel_id, survey_date DESC);",
            reverse_sql="DROP INDEX IF EXISTS idx_survey_history_parcel_date;"
        ),
    ]
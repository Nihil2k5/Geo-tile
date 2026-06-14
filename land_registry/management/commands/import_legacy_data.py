import csv
import os
import json
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from land_registry.models import Parcel
from django.core.files.base import ContentFile
from django.utils import timezone
from land_registry.utils.ipfs import upload_to_ipfs
from land_registry.blockchain.contracts import ContractManager
from land_registry.utils.document_processor import DocumentProcessor

User = get_user_model()

class Command(BaseCommand):
    help = 'Import legacy land registry data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file containing legacy data')
        parser.add_argument('--documents_dir', type=str, help='Directory containing legacy documents', default=None)
        parser.add_argument('--skip-blockchain', action='store_true', help='Skip blockchain registration')
        parser.add_argument('--default-surveyor', type=int, help='Default surveyor ID if not specified in CSV')
        parser.add_argument('--default-owner', type=int, help='Default owner ID if not specified in CSV')
        parser.add_argument('--use-ai', action='store_true', help='Use AI to extract data from legacy documents')
        parser.add_argument('--skip-extraction', action='store_true', help='Skip AI extraction even if --use-ai is specified')

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        documents_dir = options['documents_dir']
        skip_blockchain = options['skip_blockchain']
        default_surveyor_id = options['default_surveyor']
        default_owner_id = options['default_owner']
        use_ai = options['use_ai']
        skip_extraction = options['skip_extraction']

        # Initialize document processor if AI extraction is enabled
        document_processor = None
        if use_ai and not skip_extraction:
            document_processor = DocumentProcessor()
            self.stdout.write(self.style.SUCCESS('AI document processing enabled'))

        if not os.path.exists(csv_file):
            raise CommandError(f'CSV file does not exist: {csv_file}')
        
        if documents_dir and not os.path.exists(documents_dir):
            raise CommandError(f'Documents directory does not exist: {documents_dir}')
        
        # Get default users if specified
        default_surveyor = None
        default_owner = None
        
        if default_surveyor_id:
            try:
                default_surveyor = User.objects.get(id=default_surveyor_id, role='surveyor')
                self.stdout.write(self.style.SUCCESS(f'Using default surveyor: {default_surveyor.get_full_name()}'))
            except User.DoesNotExist:
                raise CommandError(f'Default surveyor with ID {default_surveyor_id} does not exist or is not a surveyor')
        
        if default_owner_id:
            try:
                default_owner = User.objects.get(id=default_owner_id, role='citizen')
                self.stdout.write(self.style.SUCCESS(f'Using default owner: {default_owner.get_full_name()}'))
            except User.DoesNotExist:
                raise CommandError(f'Default owner with ID {default_owner_id} does not exist or is not a citizen')
        
        # Initialize contract manager if needed
        contract_manager = None if skip_blockchain else ContractManager()
        
        # Process CSV file
        imported_count = 0
        errors = []
        
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            
            # Validate required fields
            required_fields = ['location', 'area', 'coordinates']
            for field in required_fields:
                if field not in reader.fieldnames:
                    raise CommandError(f'CSV file is missing required field: {field}')
            
            for row in reader:
                try:
                    # Get or use default owner
                    owner = None
                    if 'owner_id' in row and row['owner_id']:
                        try:
                            owner = User.objects.get(id=row['owner_id'], role='citizen')
                        except User.DoesNotExist:
                            self.stdout.write(self.style.WARNING(f'Owner with ID {row["owner_id"]} not found, using default'))
                    
                    if not owner:
                        if not default_owner:
                            self.stdout.write(self.style.ERROR(f'No owner specified for row and no default owner provided'))
                            errors.append(f'Row {reader.line_num}: No owner specified')
                            continue
                        owner = default_owner
                    
                    # Get or use default surveyor
                    surveyor = None
                    if 'surveyor_id' in row and row['surveyor_id']:
                        try:
                            surveyor = User.objects.get(id=row['surveyor_id'], role='surveyor')
                        except User.DoesNotExist:
                            self.stdout.write(self.style.WARNING(f'Surveyor with ID {row["surveyor_id"]} not found, using default'))
                    
                    if not surveyor:
                        if not default_surveyor:
                            self.stdout.write(self.style.ERROR(f'No surveyor specified for row and no default surveyor provided'))
                            errors.append(f'Row {reader.line_num}: No surveyor specified')
                            continue
                        surveyor = default_surveyor
                    
                    # Parse coordinates
                    try:
                        coordinates = json.loads(row['coordinates'])
                    except json.JSONDecodeError:
                        self.stdout.write(self.style.ERROR(f'Invalid coordinates JSON in row {reader.line_num}'))
                        errors.append(f'Row {reader.line_num}: Invalid coordinates JSON')
                        continue
                    
                    # Parse area
                    try:
                        area = float(row['area'])
                        if area <= 0:
                            self.stdout.write(self.style.ERROR(f'Area must be positive in row {reader.line_num}'))
                            errors.append(f'Row {reader.line_num}: Area must be positive')
                            continue
                    except ValueError:
                        self.stdout.write(self.style.ERROR(f'Invalid area value in row {reader.line_num}'))
                        errors.append(f'Row {reader.line_num}: Invalid area value')
                        continue
                    
                    # Get location
                    location = row['location']
                    if not location:
                        self.stdout.write(self.style.ERROR(f'Location is required in row {reader.line_num}'))
                        errors.append(f'Row {reader.line_num}: Location is required')
                        continue
                    
                    # Get optional description
                    description = row.get('description', '')
                    
                    # Create parcel object
                    parcel = Parcel(
                        owner=owner,
                        surveyor=surveyor,
                        area=area,
                        coordinates=coordinates,
                        location=location,
                        description=description,
                        status='pending',
                        is_legacy=True
                    )
                    
                    # Handle legacy document if provided
                    if documents_dir and 'document_file' in row and row['document_file']:
                        document_path = os.path.join(documents_dir, row['document_file'])
                        if os.path.exists(document_path):
                            with open(document_path, 'rb') as doc_file:
                                file_name = os.path.basename(document_path)
                                parcel.legacy_document.save(file_name, ContentFile(doc_file.read()))
                                
                                # Process document with AI if enabled
                                if document_processor:
                                    try:
                                        self.stdout.write(self.style.SUCCESS(f'Processing document with AI: {document_path}'))
                                        extracted_data = document_processor.process_document(document_path)
                                        
                                        # Update parcel with extracted data if available
                                        if extracted_data:
                                            self.stdout.write(self.style.SUCCESS(f'Document type detected: {extracted_data.get("document_type", "unknown")}'))
                                            
                                            # Update owner name if available and no owner specified
                                            if extracted_data.get('owner_name') and (not owner or owner == default_owner):
                                                self.stdout.write(self.style.SUCCESS(f'Extracted owner name: {extracted_data["owner_name"]}'))
                                            
                                            # Update coordinates if available and not specified in CSV
                                            if extracted_data.get('coordinates') and (not coordinates or coordinates == []):
                                                try:
                                                    # Try to parse coordinates from extracted text
                                                    coords_text = extracted_data['coordinates']
                                                    self.stdout.write(self.style.SUCCESS(f'Extracted coordinates: {coords_text}'))
                                                except Exception as e:
                                                    self.stdout.write(self.style.WARNING(f'Could not parse extracted coordinates: {str(e)}'))
                                            
                                            # Update area if available and not specified in CSV
                                            if extracted_data.get('area') and (not area or area == 0):
                                                self.stdout.write(self.style.SUCCESS(f'Extracted area: {extracted_data["area"]}'))
                                            
                                            # Update location if available and not specified in CSV
                                            if extracted_data.get('address') and (not location or location == ''):
                                                parcel.location = extracted_data['address']
                                                self.stdout.write(self.style.SUCCESS(f'Updated location from document: {extracted_data["address"]}'))
                                    except Exception as e:
                                        self.stdout.write(self.style.ERROR(f'Error processing document with AI: {str(e)}'))
                        else:
                            self.stdout.write(self.style.WARNING(f'Document file not found: {document_path}'))
                    
                    # Save parcel to database
                    parcel.save()
                    
                    # Register on blockchain if not skipped
                    if not skip_blockchain and owner.wallet_address:
                        try:
                            # Upload to IPFS
                            ipfs_hash = upload_to_ipfs({
                                'parcel_id': str(parcel.id),
                                'owner': owner.wallet_address,
                                'area': area,
                                'coordinates': coordinates,
                                'location': location,
                                'description': description,
                                'is_legacy': True
                            })
                            
                            # Register on blockchain
                            # Check if already exists on blockchain
                            if contract_manager.parcel_exists(str(parcel.id)):
                                self.stdout.write(self.style.WARNING(f'Parcel {parcel.id} already exists on blockchain, linking instead'))
                                try:
                                    blockchain_details = contract_manager.get_land_details(str(parcel.id))
                                    tx_hash = f"RECOVERED_FROM_CHAIN_TOKEN_{blockchain_details.get('token_id', 'UNKNOWN')}"
                                except Exception:
                                    tx_hash = f"RECOVERED_FROM_CHAIN_{parcel.id}"
                            else:
                                tx_hash = contract_manager.register_land(
                                    str(parcel.id),
                                    owner.wallet_address,
                                    ipfs_hash,
                                    area,
                                    ipfs_hash
                                )
                            
                            # Update parcel with transaction hash
                            parcel.blockchain_tx_hash = tx_hash
                            parcel.save()
                            
                            self.stdout.write(self.style.SUCCESS(f'Registered parcel {parcel.id} on blockchain with tx: {tx_hash}'))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'Blockchain registration failed for parcel {parcel.id}: {str(e)}'))
                            errors.append(f'Row {reader.line_num}: Blockchain registration failed: {str(e)}')
                    
                    imported_count += 1
                    self.stdout.write(self.style.SUCCESS(f'Imported legacy parcel: {parcel.id}'))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error processing row {reader.line_num}: {str(e)}'))
                    errors.append(f'Row {reader.line_num}: {str(e)}')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Import completed. Successfully imported {imported_count} parcels.'))
        if errors:
            self.stdout.write(self.style.WARNING(f'Encountered {len(errors)} errors:'))
            for error in errors:
                self.stdout.write(f'  - {error}')
# GeoLedger - Blockchain-based Land Registry System

This application is a land registry system that uses blockchain technology to manage land parcels and property transfers.

## Prerequisites

- Python 3.11 or higher
- Node.js 14.0.0 or higher
- npm 6.0.0 or higher

## Installation

### 1. Set up the Python Environment

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Set up the Blockchain Environment

```bash
# Navigate to the blockchain directory
cd blockchain

# Install Node.js dependencies
npm install

# Start the local Hardhat network
npx hardhat node

# In a new terminal, deploy the smart contracts
npx hardhat run scripts/deploy.js --network localhost
```

### 3. Set up the Django Application

```bash
# Make sure you're in the project root directory
# Apply database migrations
python manage.py migrate

# Create a superuser (admin account)
python manage.py createsuperuser

# Start the Django development server
python manage.py runserver
```

## Running the Application

1. Start the Hardhat network (if not already running):
```bash
cd blockchain
npx hardhat node
```

2. In a separate terminal, start the Django server:
```bash
python manage.py runserver
```

3. Access the application:
- Main application: http://127.0.0.1:8000
- Admin interface: http://127.0.0.1:8000/admin

## Features

- User Registration and Authentication
- Land Parcel Registration
- Property Transfer Management
- Dispute Resolution System
- Blockchain-based Transaction Records
- QR Code Generation for Properties

## Project Structure

- `blockchain/` - Smart contracts and blockchain configuration
  - `contracts/` - Solidity smart contracts
  - `scripts/` - Deployment scripts
- `land_registry/` - Main Django application
  - `blockchain/` - Blockchain interaction layer
  - `templates/` - HTML templates
  - `views/` - Application views and logic
- `theme/` - Custom styling and UI components

## Smart Contracts

The system includes three main smart contracts:
1. `LandRegistry.sol` - Manages land parcels and transfers
2. `UserRegistry.sol` - Handles user registration and roles
3. `DisputeManager.sol` - Manages property disputes

## Security Notes

- Make sure to keep your private keys and sensitive information secure
- Never commit `.env` files or private keys to version control
- Use secure password practices for admin accounts
- Regularly update dependencies to patch security vulnerabilities
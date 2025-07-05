# WalletTrack - Modular Architecture

## Project Structure

```
wallettrack/
├── main.py                 # Main application entry point
├── main_original_backup.py # Backup of original monolithic file
├── app/                    # Application modules
│   ├── __init__.py
│   ├── core/              # Core configuration and dependencies
│   │   ├── __init__.py
│   │   ├── config.py      # Application configuration
│   │   └── dependencies.py # Service initialization and lifespan
│   ├── api/               # API route handlers
│   │   ├── __init__.py
│   │   ├── wallets.py     # Wallet management endpoints
│   │   ├── transactions.py # Transaction endpoints
│   │   ├── balances.py    # Balance and history endpoints
│   │   ├── tokens.py      # Token management endpoints
│   │   └── system.py      # System status and monitoring
│   ├── services/          # Business logic layer
│   │   ├── __init__.py
│   │   ├── wallet_service.py      # Wallet business logic
│   │   ├── transaction_service.py # Transaction business logic
│   │   └── balance_service.py     # Balance business logic
│   └── websocket_handler.py # WebSocket management
├── templates/             # HTML templates
├── static/               # Static files (CSS, JS)
├── database.py           # Database models and connection
├── schemas.py            # Pydantic schemas
├── tron_service.py       # TRON blockchain service
├── eth_service.py        # Ethereum blockchain service
├── eth_monitor.py        # Ethereum monitoring
├── websocket_manager.py  # WebSocket connection manager
└── requirements.txt      # Python dependencies
```

## Architecture Benefits

### 🎯 **Separation of Concerns**
- **API Layer** (`app/api/`): HTTP endpoints and request/response handling
- **Service Layer** (`app/services/`): Business logic and data processing
- **Core Layer** (`app/core/`): Configuration and shared dependencies

### 📦 **Modular Design**
- **Wallet Management**: User wallet operations
- **Transaction Processing**: Real-time and historical transaction handling
- **Balance Tracking**: Balance history and portfolio management
- **Token Discovery**: Token information and verification
- **System Monitoring**: Health checks and status reporting

### 🔧 **Maintainability**
- **Single Responsibility**: Each module has a clear, focused purpose
- **Easy Testing**: Individual components can be tested in isolation
- **Scalable**: New features can be added without affecting existing code
- **Readable**: Code is organized logically and easy to navigate

## Key Features Preserved

✅ All original functionality maintained  
✅ Real-time WebSocket updates  
✅ Multi-blockchain support (TRON/Ethereum)  
✅ Transaction monitoring and filtering  
✅ Balance history tracking  
✅ Legacy API compatibility  
✅ Scam token filtering  

## Configuration

All configuration is centralized in `app/core/config.py`:
- Environment variables
- Default values
- Application settings
- Monitoring thresholds

## Services

### WalletService
- Wallet creation and management
- Balance fetching and updates
- Multi-blockchain support

### TransactionService  
- Real-time transaction monitoring
- Historical transaction queries
- Transaction filtering and validation

### BalanceService
- Balance change tracking
- History management
- Portfolio calculations

## Running the Application

The application entry point remains the same:

```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Migration Notes

- Original `main.py` is backed up as `main_original_backup.py`
- All imports and dependencies remain the same
- No database changes required
- All API endpoints preserve the same paths and functionality
- WebSocket functionality is fully preserved

## Future Enhancements

The modular structure makes it easy to:
- Add new blockchain support
- Implement additional monitoring features
- Create comprehensive test suites
- Add API documentation
- Implement caching layers
- Add rate limiting
- Enhance error handling

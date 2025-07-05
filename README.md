# WalletTrack - Multi-Blockchain Wallet Monitor

A comprehensive cryptocurrency wallet monitoring application that tracks balances across multiple blockchains in real-time.

## Features

- **Multi-Blockchain Support**: Monitor wallets on Ethereum and TRON networks
- **Real-Time Updates**: WebSocket-based live balance monitoring
- **Token Discovery**: Automatic detection of tokens in monitored wallets
- **Scam Protection**: Built-in filtering for suspicious tokens
- **Modern Web Interface**: Clean, responsive dashboard for wallet management
- **RESTful API**: Complete REST API for wallet and balance management
- **Balance History**: Track balance changes over time

## Supported Blockchains

- **Ethereum (ETH)**: ERC-20 tokens, native ETH balance
- **TRON (TRX)**: TRC-20 tokens, native TRX balance

## Quick Start

1. **Clone and Setup**:
   ```bash
   git clone <repository-url>
   cd wallettrack
   ```

2. **Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start the Application**:
   ```bash
   ./start.sh  # On Windows: use start.bat or run commands manually
   ```

4. **Access the Dashboard**:
   Open http://localhost:8000 in your browser

## Project Structure

```
wallettrack/
├── main.py              # FastAPI application and API endpoints
├── database.py          # Database models and setup
├── schemas.py           # Pydantic schemas for API
├── eth_service.py       # Ethereum blockchain service
├── eth_monitor.py       # Ethereum balance monitoring
├── tron_service.py      # TRON blockchain service
├── websocket_manager.py # WebSocket connection management
├── templates/
│   └── index.html       # Web dashboard interface
├── requirements.txt     # Python dependencies
├── start.sh            # Application startup script
└── wallettrack.db      # SQLite database file
```

## API Endpoints

### Wallets
- `GET /api/wallets` - List all monitored wallets
- `POST /api/wallets` - Add a new wallet for monitoring
- `GET /api/wallets/{id}` - Get specific wallet details
- `DELETE /api/wallets/{id}` - Remove wallet from monitoring
- `POST /api/wallets/{id}/refresh` - Manually refresh wallet balances

### Blockchains & Tokens
- `GET /api/blockchains` - List supported blockchains
- `GET /api/tokens` - List discovered tokens

### Monitoring
- `GET /api/status` - System status and statistics
- `GET /api/summary` - Portfolio summary across all wallets
- `GET /api/wallets/{id}/transactions` - Recent transactions
- `GET /api/wallets/{id}/balance-history` - Balance change history

### WebSocket
- `WS /ws` - Real-time updates for balance changes

## Configuration

The application uses environment variables for configuration:

- **Database**: SQLite (default: `wallettrack.db`)
- **Ethereum API**: Uses public RPC endpoints with fallback
- **TRON API**: Connects to TRON mainnet
- **Monitoring Intervals**: Configurable in service files

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, Uvicorn
- **Database**: SQLite with async support
- **Blockchain APIs**: Web3.py (Ethereum), TronPy (TRON)
- **Frontend**: Vanilla JavaScript, Chart.js
- **WebSockets**: FastAPI WebSocket support
- **Deployment**: Self-contained with virtual environment

## Development

### Adding New Blockchains

1. Create a new service file (e.g., `polygon_service.py`)
2. Add blockchain entry to the database
3. Implement monitoring in a new monitor file
4. Update the main application to include the new services

### Database Schema

The application uses SQLAlchemy models:
- `Blockchain`: Supported blockchain networks
- `Wallet`: Monitored wallet addresses
- `Token`: Discovered tokens across networks
- `WalletToken`: Current balances for wallet-token pairs
- `BalanceHistory`: Historical balance changes

## Security

- No private keys are stored or required
- Only wallet addresses are monitored (read-only)
- Built-in scam token detection and filtering
- Rate limiting for external API calls

## License

This project is open source and available under the MIT License.

## Support

For issues, feature requests, or contributions, please use the project's issue tracker.
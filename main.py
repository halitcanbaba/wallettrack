"""
Main application entry point for WalletTrack
Modular structure with separated concerns
"""
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Setup logging configuration first
from log_config import setup_logging
setup_logging()

from app.core.config import APP_TITLE, APP_DESCRIPTION, APP_VERSION
from app.core.dependencies import lifespan, logger
from app.api import wallets, transactions, balances, tokens, system, orderbook
from app.websocket_handler import websocket_endpoint

# Create FastAPI app with lifespan management
app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    lifespan=lifespan
)

# Templates
templates = Jinja2Templates(directory="templates")

# Static files
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception:
    logger.warning("Static directory not found, continuing without static files")

# Include API routers
app.include_router(wallets.router)
app.include_router(transactions.router)
app.include_router(balances.router)
app.include_router(tokens.router)
app.include_router(system.router)
app.include_router(orderbook.router)

# Main page routes
@app.get("/")
async def read_root(request: Request):
    """Serve the main dashboard"""
    return templates.TemplateResponse("index_clean.html", {"request": request})

@app.get("/history")
async def history_page(request: Request):
    """Serve the balance history page"""
    return templates.TemplateResponse("history.html", {"request": request})

@app.get("/orderbook")
async def orderbook_page(request: Request):
    """Serve the orderbook monitoring page"""
    return templates.TemplateResponse("orderbook.html", {"request": request})

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket_endpoint(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

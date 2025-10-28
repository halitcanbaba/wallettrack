/**
 * Synthetic Orderbook JavaScript
 * Handles the creation and display of synthetic orderbooks
 */

class SyntheticOrderbook {
    constructor() {
        console.log('SyntheticOrderbook constructor called');
        this.legs = [];
        this.config = null;
        this.orderbook = null;
        this.legCounter = 0;
        
        console.log('Initializing config...');
        this.initializeConfig();
    }

    async initializeConfig() {
        console.log('Starting config initialization...');
        await this.loadConfig();
        console.log('Config initialization completed');
    }

    async loadConfig() {
        console.log('Loading synthetics config...');
        try {
            const response = await fetch('/api/synthetics/config');
            console.log('Config response status:', response.status);
            if (response.ok) {
                this.config = await response.json();
                console.log('Synthetics config loaded successfully:', this.config);
                console.log('Commission rates from config:', this.config.commission_rates);
                // Trigger UI updates when config loads
                this.renderLegs();
                console.log('Legs re-rendered after config load');
            } else {
                console.warn('Failed to load synthetics config:', response.status);
            }
        } catch (error) {
            console.error('Error loading synthetics config:', error);
        }
    }

    addLeg(exchange = '', symbol = '', side = 'sell') {
        const leg = {
            id: Date.now() + Math.random(),
            exchange: exchange,
            symbol: symbol,
            side: side,
            status: 'unknown',
            commission: 0
        };
        this.legs.push(leg);
        this.renderLegs();
        return leg;
    }

    removeLeg(legId) {
        this.legs = this.legs.filter(leg => leg.id !== legId);
        this.renderLegs();
        this.updateLegsStatus();
    }

    updateLeg(legId, field, value) {
        const leg = this.legs.find(l => l.id === legId);
        if (leg) {
            leg[field] = value;
            this.updateLegsStatus();
        }
    }

    renderLegs() {
        const container = document.getElementById('legs-container');
        container.innerHTML = '';

        this.legs.forEach(leg => {
            const legDiv = document.createElement('div');
            legDiv.className = 'leg-container';
            legDiv.innerHTML = `
                <div class="leg-grid">
                    <select class="leg-select exchange-select" onchange="syntheticOrderbook.updateLeg(${leg.id}, 'exchange', this.value)">
                        <option value="">Exchange</option>
                        <option value="binance" ${leg.exchange === 'binance' ? 'selected' : ''}>Binance</option>
                        <option value="cointr" ${leg.exchange === 'cointr' ? 'selected' : ''}>CoinTR</option>
                        <option value="whitebit" ${leg.exchange === 'whitebit' ? 'selected' : ''}>WhiteBit</option>
                        <option value="okx" ${leg.exchange === 'okx' ? 'selected' : ''}>OKX</option>
                    </select>
                    
                    <input type="text" 
                           class="leg-input symbol-input"
                           value="${leg.symbol}" 
                           placeholder="ETHUSDT"
                           onchange="syntheticOrderbook.updateLeg(${leg.id}, 'symbol', this.value.toUpperCase())">
                    
                    <select class="leg-select side-select" onchange="syntheticOrderbook.updateLeg(${leg.id}, 'side', this.value)">
                        <option value="sell" ${leg.side === 'sell' ? 'selected' : ''}>Sell</option>
                        <option value="buy" ${leg.side === 'buy' ? 'selected' : ''}>Buy</option>
                    </select>
                    
                    <div class="leg-status">
                        <div class="status-dot ${leg.status === 'available' ? 'status-active' : 'status-inactive'}" id="status-${leg.id}"></div>
                        <span id="status-text-${leg.id}">${leg.status}</span>
                    </div>
                    
                    <button class="remove-leg-btn" onclick="syntheticOrderbook.removeLeg(${leg.id})" ${this.legs.length <= 2 ? 'disabled' : ''}>
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            `;
            container.appendChild(legDiv);
        });
    }

    updateLegsStatus() {
        const statusContainer = document.getElementById('legs-status-list');
        
        if (this.legs.length === 0) {
            statusContainer.innerHTML = '<p style="color: var(--text-secondary); font-style: italic;">No legs configured yet</p>';
            return;
        }

        let statusHtml = '';
        this.legs.forEach((leg, index) => {
            const commission = this.getCommissionForExchange(leg.exchange);
            statusHtml += `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-color);">
                    <span><strong>Leg ${index + 1}:</strong> ${leg.exchange} ${leg.symbol} (${leg.side})</span>
                    <span style="color: var(--text-secondary); font-size: 12px;">${commission} bps</span>
                </div>
            `;
        });
        
        statusContainer.innerHTML = statusHtml;
    }

    getCommissionForExchange(exchange) {
        console.log('Getting commission for exchange:', exchange);
        console.log('Current config:', this.config);
        
        // Get commission from loaded config
        if (this.config && this.config.commission_rates) {
            const rate = this.config.commission_rates[exchange] || 10;
            console.log('Commission from config:', rate);
            return rate;
        }
        
        // Fallback to default values if config not loaded
        console.log('Using fallback commission values');
        const defaultCommissions = {
            'binance': 5,
            'cointr': 3,
            'whitebit': 3.8,
            'okx': 5
        };
        const fallbackRate = defaultCommissions[exchange] || 10;
        console.log('Fallback commission:', fallbackRate);
        return fallbackRate;
    }

    async generateOrderbook() {
        if (this.legs.length < 2) {
            this.showError('At least 2 legs are required');
            return;
        }

        const depth = parseInt(document.getElementById('depth').value) || 5;
        
        // Collect current leg data from DOM
        const legContainers = document.querySelectorAll('.leg-container');
        const requestData = {
            legs: [],
            depth: depth
        };

        // Extract values from DOM
        legContainers.forEach((container, index) => {
            const exchange = container.querySelector('.exchange-select').value;
            const symbol = container.querySelector('.symbol-input').value;
            const side = container.querySelector('.side-select').value;
            
            requestData.legs.push({
                exchange: exchange,
                symbol: symbol,
                side: side
            });
            
            // Update our internal state too
            if (this.legs[index]) {
                this.legs[index].exchange = exchange;
                this.legs[index].symbol = symbol;
                this.legs[index].side = side;
            }
        });

        // Validate legs
        for (const leg of requestData.legs) {
            if (!leg.exchange || !leg.symbol || !leg.side) {
                this.showError('All legs must have exchange, symbol, and side specified');
                return;
            }
        }

        try {
            this.showLoading(true);
            
            const response = await fetch('/api/synthetics/orderbook', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();
            
            if (result.success) {
                this.lastResult = result;
                this.displayOrderbook(result);
                this.updateLegsStatusFromResult(result);
            } else {
                this.showError(result.error || 'Failed to generate orderbook');
            }
        } catch (error) {
            console.error('Error generating orderbook:', error);
            this.showError('Network error. Please try again.');
        } finally {
            this.showLoading(false);
        }
    }

    displayOrderbook(result) {
        // Show results section
        document.getElementById('result-section').style.display = 'block';
        document.getElementById('no-results-placeholder').style.display = 'none';
        
        // Update title
        document.getElementById('result-title').textContent = `${result.synthetic_pair}`;
        
        // Get the single orderbook table
        const orderbookTable = document.getElementById('orderbook-table');
        orderbookTable.innerHTML = '';
        
        // Combine and sort orders for exchange-style display
        const allOrders = [];
        
        // Add asks (reverse order for exchange style - highest price first)
        if (result.asks && result.asks.length > 0) {
            result.asks.reverse().forEach(ask => {
                allOrders.push({
                    price: ask.price,
                    amount: ask.amount,
                    total: (ask.price * ask.amount).toFixed(2),
                    side: 'ask'
                });
            });
        }
        
        // Add bids (highest price first)
        if (result.bids && result.bids.length > 0) {
            result.bids.forEach(bid => {
                allOrders.push({
                    price: bid.price,
                    amount: bid.amount,
                    total: (bid.price * bid.amount).toFixed(2),
                    side: 'bid'
                });
            });
        }
        
        // Display all orders
        if (allOrders.length > 0) {
            allOrders.forEach(order => {
                const row = orderbookTable.insertRow();
                row.className = order.side === 'ask' ? 'asks-row' : 'bids-row';
                row.innerHTML = `
                    <td>${this.formatPrice(order.price)}</td>
                    <td>${this.formatAmount(order.amount)}</td>
                    <td>${this.formatPrice(order.total)}</td>
                    <td><span class="side-badge side-${order.side}">${order.side}</span></td>
                `;
            });
        } else {
            orderbookTable.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-secondary);">No orders available</td></tr>';
        }
    }

    updateLegsStatusFromResult(result) {
        if (result.legs) {
            result.legs.forEach((legResult, index) => {
                if (this.legs[index]) {
                    this.legs[index].status = legResult.available ? 'available' : 'unavailable';
                    
                    // Update status indicator
                    const statusDot = document.getElementById(`status-${this.legs[index].id}`);
                    const statusText = document.getElementById(`status-text-${this.legs[index].id}`);
                    
                    if (statusDot && statusText) {
                        statusDot.className = `status-dot ${legResult.available ? 'status-active' : 'status-inactive'}`;
                        statusText.textContent = legResult.available ? 'available' : 'unavailable';
                    }
                }
            });
        }
        
        this.updateLegsStatus();
    }

    formatPrice(price) {
        const num = parseFloat(price);
        if (num >= 1000) {
            return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        } else if (num >= 1) {
            return num.toFixed(4);
        } else {
            return num.toFixed(8);
        }
    }

    formatAmount(amount) {
        const num = parseFloat(amount);
        if (num >= 1000) {
            return num.toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
        } else if (num >= 1) {
            return num.toFixed(6);
        } else {
            return num.toFixed(8);
        }
    }

    toggleAutoRefresh() {
        this.isAutoRefreshEnabled = !this.isAutoRefreshEnabled;
        
        const toggle = document.getElementById('auto-refresh-toggle');
        toggle.checked = this.isAutoRefreshEnabled;
        
        if (this.isAutoRefreshEnabled) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }

    startAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
        }
        
        this.autoRefreshInterval = setInterval(() => {
            if (this.lastResult) {
                this.generateOrderbook();
            }
        }, this.refreshIntervalMs);
        
        console.log('Auto-refresh started (15s interval)');
    }

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
        
        console.log('Auto-refresh stopped');
    }

    showLoading(loading) {
        const generateBtn = document.querySelector('.btn.btn-primary');
        if (loading) {
            generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
            generateBtn.disabled = true;
        } else {
            generateBtn.innerHTML = '<i class="fas fa-play"></i> Generate Orderbook';
            generateBtn.disabled = false;
        }
    }

    showError(message) {
        // Simple alert for now - could be enhanced with a toast notification
        alert('Error: ' + message);
    }

    // Cleanup on page unload
    cleanup() {
        this.stopAutoRefresh();
    }
}

// Global instance
const syntheticOrderbook = new SyntheticOrderbook();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    syntheticOrderbook.cleanup();
});

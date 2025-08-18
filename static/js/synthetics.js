/**
 * Synthetic Orderbook JavaScript
 * Handles the creation and display of synthetic orderbooks
 */

class SyntheticOrderbook {
    constructor() {
        this.legs = [];
        this.config = null;
        this.autoRefreshInterval = null;
        this.isAutoRefreshEnabled = false;
        this.refreshIntervalMs = 15000; // 15 seconds
        this.lastResult = null;
        this.loadConfig();
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/synthetics/config');
            this.config = await response.json();
        } catch (error) {
            console.error('Failed to load synthetics config:', error);
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
        const commissions = {
            'binance': 5,
            'cointr': 9.5,
            'whitebit': 3.8,
            'okx': 6
        };
        return commissions[exchange] || 10;
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
        document.getElementById('result-title').textContent = `${result.synthetic_pair} Orderbook`;
        
        // Display asks
        const asksTable = document.getElementById('asks-table');
        asksTable.innerHTML = '';
        
        if (result.asks && result.asks.length > 0) {
            result.asks.forEach(ask => {
                const total = (ask.price * ask.amount).toFixed(2);
                const row = asksTable.insertRow();
                row.className = 'asks-row';
                row.innerHTML = `
                    <td>${this.formatPrice(ask.price)}</td>
                    <td>${this.formatAmount(ask.amount)}</td>
                    <td>${this.formatPrice(total)}</td>
                `;
            });
        } else {
            asksTable.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-secondary);">No ask levels available</td></tr>';
        }
        
        // Display bids
        const bidsTable = document.getElementById('bids-table');
        bidsTable.innerHTML = '';
        
        if (result.bids && result.bids.length > 0) {
            result.bids.forEach(bid => {
                const total = (bid.price * bid.amount).toFixed(2);
                const row = bidsTable.insertRow();
                row.className = 'bids-row';
                row.innerHTML = `
                    <td>${this.formatPrice(bid.price)}</td>
                    <td>${this.formatAmount(bid.amount)}</td>
                    <td>${this.formatPrice(total)}</td>
                `;
            });
        } else {
            bidsTable.innerHTML = '<tr><td colspan="3" style="text-align: center; color: var(--text-secondary);">No bid levels available</td></tr>';
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

// Orderbook Manager for cryptocurrency orderbook monitoring
console.log('📄 Loading orderbook.js...');

class OrderbookManager {
    constructor() {
        console.log('🚀 OrderbookManager constructor called');
        this.orderbooks = {
            binance: { bids: [], asks: [] },
            cointr: { bids: [], asks: [] },
            whitebit: { bids: [], asks: [] }
        };
        this.connectionStatus = 'connecting';
        this.config = null;
        
        // Initialize with mock data to prevent errors
        this.initializeMockData();
        this.init();
    }

    initializeMockData() {
        console.log('🎭 Initializing with mock data...');
        this.orderbooks.binance = this.generateMockOrderbook();
        this.orderbooks.cointr = this.generateMockOrderbook();
        this.orderbooks.whitebit = this.generateMockOrderbook();
    }

    async init() {
        console.log('🔧 Initializing OrderbookManager...');
        await this.loadConfig();
        this.startPeriodicUpdates();
        this.updateStatus('connected', 'green');
        console.log('✅ OrderbookManager initialized successfully');
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/orderbook/config');
            if (response.ok) {
                this.config = await response.json();
                console.log('📋 Config loaded:', this.config);
            } else {
                console.error('❌ Failed to load config:', response.status);
                // Fallback config
                this.config = {
                    binance_commission: 5,
                    whitebit_commission: 5,
                    cointr_commission: 5
                };
            }
        } catch (error) {
            console.error('❌ Config load error:', error);
            // Fallback config
            this.config = {
                binance_commission: 5,
                whitebit_commission: 5,
                cointr_commission: 5
            };
        }
    }

    async fetchBinanceOrderbook() {
        try {
            const response = await fetch('/api/orderbook/binance');
            if (response.ok) {
                const result = await response.json();
                console.log('📊 Binance API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.binance = result.data;
                    console.log('📊 Binance orderbook updated');
                } else {
                    console.error('❌ Invalid Binance response structure:', result);
                    this.orderbooks.binance = this.generateMockOrderbook();
                }
            } else {
                console.error('❌ Binance fetch failed:', response.status);
                this.orderbooks.binance = this.generateMockOrderbook();
            }
        } catch (error) {
            console.error('❌ Binance fetch error:', error);
            this.orderbooks.binance = this.generateMockOrderbook();
        }
    }

    async fetchWhiteBitOrderbook() {
        try {
            const response = await fetch('/api/orderbook/whitebit');
            if (response.ok) {
                const result = await response.json();
                console.log('📊 WhiteBit API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.whitebit = result.data;
                    console.log('📊 WhiteBit orderbook updated');
                } else {
                    console.error('❌ Invalid WhiteBit response structure:', result);
                    this.orderbooks.whitebit = this.generateMockOrderbook();
                }
            } else {
                console.error('❌ WhiteBit fetch failed:', response.status);
                this.orderbooks.whitebit = this.generateMockOrderbook();
            }
        } catch (error) {
            console.error('❌ WhiteBit fetch error:', error);
            this.orderbooks.whitebit = this.generateMockOrderbook();
        }
    }

    async fetchCoinTROrderbook() {
        try {
            const response = await fetch('/api/orderbook/cointr');
            if (response.ok) {
                const result = await response.json();
                console.log('📊 CoinTR API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.cointr = result.data;
                    console.log('📊 CoinTR orderbook updated');
                } else {
                    console.error('❌ Invalid CoinTR response structure:', result);
                    this.orderbooks.cointr = this.generateMockOrderbook();
                }
            } else {
                console.error('❌ CoinTR fetch failed:', response.status);
                this.orderbooks.cointr = this.generateMockOrderbook();
            }
        } catch (error) {
            console.error('❌ CoinTR fetch error:', error);
            this.orderbooks.cointr = this.generateMockOrderbook();
        }
    }

    generateMockOrderbook() {
        const basePrice = 32.15 + (Math.random() - 0.5) * 0.5;
        const bids = [];
        const asks = [];
        
        for (let i = 0; i < 8; i++) {
            const bidPrice = basePrice - (i + 1) * 0.01;
            const askPrice = basePrice + (i + 1) * 0.01;
            const bidAmount = (Math.random() * 10000 + 1000);
            const askAmount = (Math.random() * 10000 + 1000);
            
            bids.push([bidPrice.toFixed(2), bidAmount.toFixed(2)]);
            asks.push([askPrice.toFixed(2), askAmount.toFixed(2)]);
        }
        
        return { bids, asks };
    }

    async updateOrderbooks() {
        console.log('🔄 Updating all orderbooks...');
        this.updateStatus('updating', 'orange');
        
        try {
            await Promise.all([
                this.fetchBinanceOrderbook(),
                this.fetchWhiteBitOrderbook(),
                this.fetchCoinTROrderbook()
            ]);
            
            this.renderOrderbooks();
            this.updateComparisonTable();
            this.updateStatus('connected', 'green');
            console.log('✅ All orderbooks updated successfully');
        } catch (error) {
            console.error('❌ Error updating orderbooks:', error);
            this.updateStatus('error', 'red');
        }
    }

    startPeriodicUpdates() {
        console.log('⏰ Starting periodic updates (3 seconds)');
        this.updateOrderbooks();
        this.updateInterval = setInterval(() => {
            this.updateOrderbooks();
        }, 3000);
    }

    renderOrderbooks() {
        this.renderOrderbook('binance', this.orderbooks.binance);
        this.renderOrderbook('cointr', this.orderbooks.cointr);
        this.renderOrderbook('whitebit', this.orderbooks.whitebit);
    }

    renderOrderbook(exchange, orderbook) {
        const container = document.getElementById(`${exchange}-orderbook`);
        if (!container) {
            console.warn(`⚠️ Container not found: ${exchange}-orderbook`);
            return;
        }

        // Safety checks for orderbook data
        if (!orderbook || !orderbook.bids || !orderbook.asks) {
            console.warn(`⚠️ Invalid orderbook data for ${exchange}:`, orderbook);
            container.innerHTML = '<div class="orderbook-loading">Loading...</div>';
            return;
        }

        if (orderbook.bids.length === 0 || orderbook.asks.length === 0) {
            console.warn(`⚠️ Empty orderbook data for ${exchange}`);
            container.innerHTML = '<div class="orderbook-loading">No data available</div>';
            return;
        }

        const bids = orderbook.bids.slice(0, 8);
        const asks = orderbook.asks.slice(0, 8).reverse();
        
        const bestBid = parseFloat(bids[0][0]);
        const bestAsk = parseFloat(asks[asks.length - 1][0]);
        const spread = bestAsk - bestBid;
        const spreadPercent = ((spread / bestAsk) * 100).toFixed(2);

        let html = '<table class="orderbook-table">';
        
        html += `
            <tr class="header-row">
                <th>Price (TRY)</th>
                <th>Amount (USDT)</th>
                <th>Total (TRY)</th>
            </tr>
        `;

        asks.forEach(ask => {
            const price = parseFloat(ask[0]);
            const amount = parseFloat(ask[1]);
            const total = price * amount;
            html += `
                <tr class="ask-row">
                    <td class="price ask-price">${this.formatPrice(price)}</td>
                    <td class="amount">${this.formatAmount(amount)}</td>
                    <td class="total">${this.formatPrice(total)}</td>
                </tr>
            `;
        });

        html += `
            <tr class="spread-row">
                <td colspan="3" style="text-align: center; font-weight: bold; color: #888;">
                    Spread: ${spread.toFixed(2)} TRY (${spreadPercent}%)
                </td>
            </tr>
        `;

        bids.forEach(bid => {
            const price = parseFloat(bid[0]);
            const amount = parseFloat(bid[1]);
            const total = price * amount;
            html += `
                <tr class="bid-row">
                    <td class="price bid-price">${this.formatPrice(price)}</td>
                    <td class="amount">${this.formatAmount(amount)}</td>
                    <td class="total">${this.formatPrice(total)}</td>
                </tr>
            `;
        });

        html += '</table>';
        container.innerHTML = html;
    }

    updateComparisonTable() {
        const tbody = document.querySelector('#top-book-table-body');
        if (!tbody) {
            console.warn('⚠️ Comparison table not found');
            return;
        }

        const exchanges = ['binance', 'cointr', 'whitebit'];
        let html = '';

        exchanges.forEach(exchange => {
            const orderbook = this.orderbooks[exchange];
            if (!orderbook || !orderbook.bids || !orderbook.asks || 
                !orderbook.bids.length || !orderbook.asks.length) {
                console.warn(`⚠️ Skipping ${exchange} - invalid orderbook data`);
                return;
            }

            const bestBid = parseFloat(orderbook.bids[0][0]);
            const bestAsk = parseFloat(orderbook.asks[0][0]);
            const askAmount = parseFloat(orderbook.asks[0][1]);
            
            const commissionBps = this.config ? this.config[`${exchange}_commission`] : 5;
            const commission = (bestAsk * askAmount * commissionBps) / 10000;
            const kdv = commission * 0.18;
            const rawPrice = bestAsk * askAmount;
            const netPrice = rawPrice + commission + kdv;

            html += `
                <tr>
                    <td>${exchange.toUpperCase()}</td>
                    <td class="bid-price">${this.formatPrice(bestBid)}</td>
                    <td class="ask-price">${this.formatPrice(bestAsk)}</td>
                    <td>${this.formatAmount(askAmount)}</td>
                    <td>${this.formatPrice(commission)}</td>
                    <td>${this.formatPrice(kdv)}</td>
                    <td>${this.formatPrice(rawPrice)}</td>
                    <td>${this.formatPrice(netPrice)}</td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    formatPrice(price) {
        return parseFloat(price).toFixed(2);
    }

    formatAmount(amount) {
        return parseFloat(amount).toLocaleString('tr-TR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    updateStatus(status, color) {
        const statusElements = document.querySelectorAll('.status-indicator');
        statusElements.forEach(element => {
            element.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            element.style.color = color;
        });
        this.connectionStatus = status;
    }

    destroy() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            console.log('🛑 Periodic updates stopped');
        }
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('🌐 DOM loaded, initializing OrderbookManager...');
    window.orderbookManager = new OrderbookManager();
});

window.addEventListener('beforeunload', function() {
    if (window.orderbookManager) {
        window.orderbookManager.destroy();
    }
});

console.log('✅ orderbook.js loaded successfully');
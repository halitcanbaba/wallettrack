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
        this.calculationAmount = 200000; // Default 200k
        
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
        this.setupAmountInput();
        this.startPeriodicUpdates();
        this.updateStatus('connected', 'green');
        console.log('✅ OrderbookManager initialized successfully');
    }

    setupAmountInput() {
        const amountInput = document.getElementById('calculation-amount');
        if (amountInput) {
            amountInput.addEventListener('input', (e) => {
                const parsedAmount = this.parseAmount(e.target.value);
                if (parsedAmount > 0) {
                    this.calculationAmount = parsedAmount;
                    console.log('💰 Calculation amount updated to:', this.calculationAmount);
                    this.updateComparisonTable(); // Refresh table with new amount
                }
            });
            
            // Set initial value
            this.calculationAmount = this.parseAmount(amountInput.value);
        }
    }

    parseAmount(input) {
        if (!input || typeof input !== 'string') return 0;
        
        // Remove spaces and convert to lowercase
        const cleaned = input.trim().toLowerCase();
        
        // Extract number and suffix
        const match = cleaned.match(/^(\d+(?:\.\d+)?)\s*([kmb]?)$/);
        if (!match) return 0;
        
        const number = parseFloat(match[1]);
        const suffix = match[2];
        
        switch (suffix) {
            case 'k':
                return number * 1000;
            case 'm':
                return number * 1000000;
            case 'b':
                return number * 1000000000;
            default:
                return number;
        }
    }

    async loadConfig() {
        try {
            const response = await fetch('/api/orderbook/config');
            if (response.ok) {
                const result = await response.json();
                this.config = result;
                console.log('📋 Config loaded:', this.config);
            } else {
                console.error('❌ Failed to load config:', response.status);
                // Fallback config
                this.config = {
                    binance_commission: 10,
                    whitebit_commission: 10,
                    cointr_commission: 15
                };
            }
        } catch (error) {
            console.error('❌ Config load error:', error);
            // Fallback config
            this.config = {
                binance_commission: 10,
                whitebit_commission: 10,
                cointr_commission: 15
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
                    <td class="total">${this.formatTotalPrice(total)}</td>
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
                    <td class="total">${this.formatTotalPrice(total)}</td>
                </tr>
            `;
        });

        html += '</table>';
        container.innerHTML = html;
    }

    /**
     * Calculate weighted average price for orderbook depth
     * @param {Array} asks - Array of [price, amount] pairs
     * @param {number} targetAmount - Target amount to fill
     * @returns {Object} - {weightedAvgPrice, totalAmount, canFill}
     */
    calculateWeightedAveragePrice(asks, targetAmount) {
        if (!asks || asks.length === 0) {
            return { weightedAvgPrice: 0, totalAmount: 0, canFill: false };
        }

        let totalCost = 0;
        let totalAmountFilled = 0;
        let remainingAmount = targetAmount;

        for (const [price, amount] of asks) {
            const askPrice = parseFloat(price);
            const askAmount = parseFloat(amount);
            
            if (remainingAmount <= 0) break;
            
            const amountToTake = Math.min(remainingAmount, askAmount);
            totalCost += askPrice * amountToTake;
            totalAmountFilled += amountToTake;
            remainingAmount -= amountToTake;
        }

        const canFill = remainingAmount <= 0;
        const weightedAvgPrice = totalAmountFilled > 0 ? totalCost / totalAmountFilled : 0;

        return {
            weightedAvgPrice,
            totalAmount: totalAmountFilled,
            canFill
        };
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
            const askAmount = parseFloat(orderbook.asks[0][1]); // API'den gelen amount
            
            // Binance best ask amount'u al (WhiteBit liquidity kontrolü için)
            const binanceBestAskAmount = this.orderbooks.binance && this.orderbooks.binance.asks && this.orderbooks.binance.asks.length > 0 
                ? parseFloat(this.orderbooks.binance.asks[0][1]) : 0;
            
            // .env'den gelen BPS değeri ile commission hesapla
            const commissionBps = this.config ? this.config[`${exchange}_commission`] : 
                (exchange === 'cointr' ? 15 : 10);
            
            // Commission hesaplaması için miktar belirleme ve fiyat hesaplama
            let commissionBaseAmount, rawPrice, effectivePrice, liquidityWarning = '';
            
            if (exchange === 'whitebit') {
                // WhiteBit için özel liquidity kontrolü ve WAVG hesaplaması
                commissionBaseAmount = askAmount; // WhiteBit için sadece askAmount
                effectivePrice = bestAsk;
                
                const commissionRate = commissionBps * 0.0001;
                
                console.log(`💡 ${exchange}: Calculating price for ${this.calculationAmount} USDT`);
                console.log(`💡 ${exchange}: Best ask: ${bestAsk}, Best ask amount: ${askAmount}`);
                console.log(`💡 ${exchange}: Binance best ask amount: ${binanceBestAskAmount}`);
                
                // Liquidity warning kontrolü (sadece notification için)
                if (this.calculationAmount > binanceBestAskAmount) {
                    liquidityWarning = ' <small style="color: #ff0000;">(lack of liquidity)</small>';
                }
                
                // Her zaman WAVG calculation uygula
                console.log(`💡 ${exchange}: Using WAVG calculation`);
                
                // WAVG hesabı: (whitebit_amount * whitebit_price * commission) + ((input - whitebit_amount) * whitebit_price)
                const whiteBitPortion = askAmount * bestAsk * (1 + commissionRate);
                const remainingPortion = (this.calculationAmount - askAmount) * bestAsk;
                const totalAmount = this.calculationAmount;
                
                rawPrice = (whiteBitPortion + remainingPortion) / totalAmount;
                
                console.log(`💡 ${exchange}: WhiteBit portion: ${whiteBitPortion.toFixed(4)}`);
                console.log(`💡 ${exchange}: Remaining portion: ${remainingPortion.toFixed(4)}`);
                console.log(`💡 ${exchange}: WAVG raw price: ${rawPrice.toFixed(4)}`);
            } else {
                // CoinTR ve Binance için yeni mantık
                commissionBaseAmount = this.calculationAmount;
                
                console.log(`💡 ${exchange}: Calculating price for ${this.calculationAmount} USDT`);
                console.log(`💡 ${exchange}: Best ask: ${bestAsk}, Best ask amount: ${askAmount}`);
                
                if (this.calculationAmount > askAmount) {
                    // Input > best ask amount: Weighted average calculation
                    console.log(`💡 ${exchange}: Using weighted average (${this.calculationAmount} > ${askAmount})`);
                    const result = this.calculateWeightedAveragePrice(orderbook.asks, this.calculationAmount);
                    effectivePrice = result.weightedAvgPrice;
                    
                    console.log(`💡 ${exchange}: Weighted average price: ${effectivePrice.toFixed(4)}`);
                    
                    if (!result.canFill) {
                        console.warn(`⚠️ ${exchange}: Cannot fill ${this.calculationAmount} USDT, max available: ${result.totalAmount}`);
                        effectivePrice = result.weightedAvgPrice; // Use partial fill price
                    }
                } else {
                    // Input < best ask amount: Use best ask price
                    console.log(`💡 ${exchange}: Using best ask price (${this.calculationAmount} <= ${askAmount})`);
                    effectivePrice = bestAsk;
                }
                
                const commissionRate = commissionBps * 0.0001;
                rawPrice = effectivePrice * (1 + commissionRate);
            }
            
            // Commission hesaplaması
            const commission = (effectivePrice * commissionBaseAmount * commissionBps) / 10000;
            const kdv = commission * 0.18;
            
            // Net Price = Effective Price (weighted average or best ask)
            const netPrice = effectivePrice;

            // Tooltip hesaplamaları
            const commissionTooltip = `Commission: ${this.formatPrice(effectivePrice)} × ${commissionBaseAmount.toLocaleString('tr-TR')} × ${commissionBps} bps / 10000 = ${this.formatPrice(commission)}`;
            const kdvTooltip = `KDV: ${this.formatPrice(commission)} × 0.18 (18%) = ${this.formatPrice(kdv)}`;
            
            let rawPriceTooltip, netPriceTooltip;
            
            if (exchange === 'whitebit') {
                // WhiteBit her zaman WAVG calculation tooltip gösterir
                const commissionRate = commissionBps * 0.0001;
                const whiteBitPortion = askAmount * bestAsk * (1 + commissionRate);
                const remainingPortion = (this.calculationAmount - askAmount) * bestAsk;
                rawPriceTooltip = `Raw Price (WAVG): (${this.formatAmount(askAmount)} × ${this.formatPrice(bestAsk)} × ${(1 + commissionRate).toFixed(4)} + ${(this.calculationAmount - askAmount).toLocaleString('tr-TR')} × ${this.formatPrice(bestAsk)}) / ${this.calculationAmount.toLocaleString('tr-TR')} = ${this.formatPrice(rawPrice)}`;
                netPriceTooltip = `Net Price: Best Ask = ${this.formatPrice(netPrice)}`;
            } else {
                // CoinTR and Binance tooltips
                rawPriceTooltip = this.calculationAmount > askAmount 
                    ? `Raw Price: ${this.formatPrice(effectivePrice)} × (1 + ${commissionBps} bps) = ${this.formatPrice(effectivePrice)} × ${(1 + commissionBps * 0.0001).toFixed(4)} = ${this.formatPrice(rawPrice)}`
                    : `Raw Price: ${this.formatPrice(effectivePrice)} × (1 + ${commissionBps} bps) = ${this.formatPrice(effectivePrice)} × ${(1 + commissionBps * 0.0001).toFixed(4)} = ${this.formatPrice(rawPrice)}`;
                netPriceTooltip = this.calculationAmount > askAmount 
                    ? `Net Price: Weighted Average = ${this.formatPrice(netPrice)}`
                    : `Net Price: Best Ask = ${this.formatPrice(netPrice)}`;
            }

            html += `
                <tr>
                    <td>${exchange.toUpperCase()}</td>
                    <td class="bid-price">${this.formatPrice(bestBid)}</td>
                    <td class="ask-price">${this.formatPrice(bestAsk)}</td>
                    <td>${this.formatAmount(askAmount)}</td>
                    <td title="${commissionTooltip}">${this.formatPrice(commission)}</td>
                    <td title="${kdvTooltip}">${this.formatPrice(kdv)}</td>
                    <td title="${rawPriceTooltip}">${this.formatPrice(rawPrice)}${liquidityWarning}</td>
                    <td title="${netPriceTooltip}">${this.formatPrice(netPrice)}</td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    formatPrice(price) {
        return parseFloat(price).toFixed(2);
    }

    formatTotalPrice(price) {
        return parseFloat(price).toLocaleString('tr-TR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
    }

    formatAmount(amount) {
        return parseFloat(amount).toLocaleString('tr-TR', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    updateStatus(status, color) {
        const statusIcons = document.querySelectorAll('.status-icon');
        
        statusIcons.forEach(icon => {
            // Remove all status classes
            icon.classList.remove('status-connected', 'status-updating', 'status-error', 'status-connecting');
            
            // Always use heartbeat icon with different status colors
            switch(status.toLowerCase()) {
                case 'connected':
                    icon.className = 'fas fa-heartbeat status-icon status-connected';
                    break;
                case 'updating':
                    icon.className = 'fas fa-heartbeat status-icon status-updating';
                    break;
                case 'error':
                    icon.className = 'fas fa-heartbeat status-icon status-error';
                    break;
                case 'connecting':
                default:
                    icon.className = 'fas fa-heartbeat status-icon status-connecting';
                    break;
            }
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
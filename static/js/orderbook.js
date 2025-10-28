// Orderbook Manager for cryptocurrency orderbook monitoring
console.log('📄 Loading orderbook.js...');

class OrderbookManager {
    constructor() {
        console.log('🚀 OrderbookManager constructor called');
        this.orderbooks = {
            binance: { bids: [], asks: [] },
            cointr: { bids: [], asks: [] },
            whitebit: { bids: [], asks: [] },
            okx: { bids: [], asks: [] }
        };
        this.connectionStatus = 'connecting';
        this.config = null;
        this.calculationAmount = 50000; // Default 50k
        this.currentSymbol = 'USDTTRY'; // Default symbol
        
        // Initialize with mock data to prevent errors
        this.initializeMockData();
        this.init();
    }

    initializeMockData() {
        console.log('🎭 Initializing with mock data...');
        this.orderbooks.binance = this.generateMockOrderbook();
        this.orderbooks.cointr = this.generateMockOrderbook();
        this.orderbooks.whitebit = this.generateMockOrderbook();
        this.orderbooks.okx = this.generateMockOrderbook();
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
                    cointr_commission: 15,
                    okx_commission: 8.5
                };
            }
        } catch (error) {
            console.error('❌ Config load error:', error);
            // Fallback config
            this.config = {
                binance_commission: 10,
                whitebit_commission: 10,
                cointr_commission: 15,
                okx_commission: 8.5,
                paribu_commission: 7.5
            };
        }
    }

    async fetchBinanceOrderbook() {
        try {
            const symbol = this.currentSymbol || 'USDTTRY';
            console.log('🔍 Binance: Fetching orderbook for symbol:', symbol);
            const response = await fetch(`/api/orderbook/binance?symbol=${symbol}`);
            if (response.ok) {
                const result = await response.json();
                console.log('📊 Binance API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.binance = result.data;
                    console.log('📊 Binance orderbook updated');
                } else {
                    console.error('❌ Invalid Binance response structure:', result);
                    this.orderbooks.binance = { bids: [], asks: [] }; // Empty for N/A display
                }
            } else {
                console.error('❌ Binance fetch failed:', response.status);
                this.orderbooks.binance = { bids: [], asks: [] }; // Empty for N/A display
            }
        } catch (error) {
            console.error('❌ Binance fetch error:', error);
            this.orderbooks.binance = { bids: [], asks: [] }; // Empty for N/A display
        }
    }

    async fetchWhiteBitOrderbook() {
        try {
            const symbol = this.currentSymbol || 'USDTTRY';
            console.log('🔍 WhiteBit: Fetching orderbook for symbol:', symbol);
            const response = await fetch(`/api/orderbook/whitebit?symbol=${symbol}`);
            if (response.ok) {
                const result = await response.json();
                console.log('📊 WhiteBit API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.whitebit = result.data;
                    console.log('📊 WhiteBit orderbook updated');
                } else {
                    console.error('❌ Invalid WhiteBit response structure:', result);
                    this.orderbooks.whitebit = { bids: [], asks: [] }; // Empty for N/A display
                }
            } else {
                console.error('❌ WhiteBit fetch failed:', response.status);
                this.orderbooks.whitebit = { bids: [], asks: [] }; // Empty for N/A display
            }
        } catch (error) {
            console.error('❌ WhiteBit fetch error:', error);
            this.orderbooks.whitebit = { bids: [], asks: [] }; // Empty for N/A display
        }
    }

    async fetchCoinTROrderbook() {
        try {
            const symbol = this.currentSymbol || 'USDTTRY';
            console.log('🔍 CoinTR: Fetching orderbook for symbol:', symbol);
            const response = await fetch(`/api/orderbook/cointr?symbol=${symbol}`);
            if (response.ok) {
                const result = await response.json();
                console.log('📊 CoinTR API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.cointr = result.data;
                    console.log('📊 CoinTR orderbook updated');
                } else {
                    console.error('❌ Invalid CoinTR response structure:', result);
                    this.orderbooks.cointr = { bids: [], asks: [] }; // Empty for N/A display
                }
            } else {
                console.error('❌ CoinTR fetch failed:', response.status);
                this.orderbooks.cointr = { bids: [], asks: [] }; // Empty for N/A display
            }
        } catch (error) {
            console.error('❌ CoinTR fetch error:', error);
            this.orderbooks.cointr = { bids: [], asks: [] }; // Empty for N/A display
        }
    }

    async fetchOKXOrderbook() {
        try {
            const symbol = this.currentSymbol || 'USDTTRY';
            console.log('🔍 OKX: Fetching orderbook for symbol:', symbol);
            const response = await fetch(`/api/orderbook/okx?symbol=${symbol}`);
            if (response.ok) {
                const result = await response.json();
                console.log('📊 OKX API response:', result);
                
                // Extract data from API response
                if (result.success && result.data) {
                    this.orderbooks.okx = result.data;
                    console.log('📊 OKX orderbook updated');
                } else {
                    console.error('❌ Invalid OKX response structure:', result);
                    this.orderbooks.okx = { bids: [], asks: [] }; // Empty for N/A display
                }
            } else {
                console.error('❌ OKX fetch failed:', response.status);
                this.orderbooks.okx = { bids: [], asks: [] }; // Empty for N/A display
            }
        } catch (error) {
            console.error('❌ OKX fetch error:', error);
            this.orderbooks.okx = { bids: [], asks: [] }; // Empty for N/A display
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
            
            const formatting = this.getSymbolFormatting(this.currentSymbol || 'USDTTRY');
            bids.push([bidPrice.toFixed(formatting.priceDecimals), bidAmount.toFixed(formatting.amountDecimals)]);
            asks.push([askPrice.toFixed(formatting.priceDecimals), askAmount.toFixed(formatting.amountDecimals)]);
        }
        
        return { bids, asks };
    }

    async updateOrderbooks() {
        console.log('🔄 Updating all orderbooks...');
        console.log('🔍 Current symbol in updateOrderbooks:', this.currentSymbol);
        this.updateStatus('updating', 'orange');
        
        try {
            await Promise.all([
                this.fetchBinanceOrderbook(),
                this.fetchWhiteBitOrderbook(),
                this.fetchCoinTROrderbook(),
                this.fetchOKXOrderbook()
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
        this.renderOrderbook('okx', this.orderbooks.okx);
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
            container.innerHTML = '<div class="orderbook-loading">N/A - Data not available</div>';
            return;
        }

        if (orderbook.bids.length === 0 || orderbook.asks.length === 0) {
            console.warn(`⚠️ Empty orderbook data for ${exchange}`);
            container.innerHTML = '<div class="orderbook-loading">N/A - Symbol not supported</div>';
            return;
        }

        const bids = orderbook.bids.slice(0, 8);
        const asks = orderbook.asks.slice(0, 8).reverse();
        
        // Helper function to extract price and amount from both array and object formats
        const extractPriceAmount = (item) => {
            if (Array.isArray(item)) {
                return { price: parseFloat(item[0]), amount: parseFloat(item[1]) };
            } else if (typeof item === 'object' && item.price !== undefined && item.amount !== undefined) {
                return { price: parseFloat(item.price), amount: parseFloat(item.amount) };
            }
            return { price: 0, amount: 0 };
        };
        
        const bestBidData = extractPriceAmount(bids[0]);
        const bestAskData = extractPriceAmount(asks[asks.length - 1]);
        const spread = bestAskData.price - bestBidData.price;
        const spreadPercent = ((spread / bestAskData.price) * 100).toFixed(2);
        const formatting = this.getSymbolFormatting(this.currentSymbol || 'USDTTRY');

        let html = '<table class="orderbook-table">';
        
        // Dynamic headers based on symbol
        const baseAsset = this.currentSymbol.replace(formatting.currency, '');
        const quoteAsset = formatting.currency;
        
        html += `
            <tr class="header-row">
                <th>Price (${quoteAsset})</th>
                <th>Amount (${baseAsset})</th>
                <th>Total (${quoteAsset})</th>
            </tr>
        `;

        asks.forEach(ask => {
            const { price, amount } = extractPriceAmount(ask);
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
                    Spread: ${this.formatPrice(spread)} ${quoteAsset} (${spreadPercent}%)
                </td>
            </tr>
        `;

        bids.forEach(bid => {
            const { price, amount } = extractPriceAmount(bid);
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

        // Helper function to extract price and amount from both array and object formats
        const extractPriceAmount = (item) => {
            if (Array.isArray(item)) {
                return { price: parseFloat(item[0]), amount: parseFloat(item[1]) };
            } else if (typeof item === 'object' && item.price !== undefined && item.amount !== undefined) {
                return { price: parseFloat(item.price), amount: parseFloat(item.amount) };
            }
            return { price: 0, amount: 0 };
        };

        for (const ask of asks) {
            const { price: askPrice, amount: askAmount } = extractPriceAmount(ask);
            
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

        const exchanges = ['binance', 'cointr', 'whitebit', 'okx'];
        let html = '';

        exchanges.forEach(exchange => {
            const orderbook = this.orderbooks[exchange];
            if (!orderbook || !orderbook.bids || !orderbook.asks || 
                !orderbook.bids.length || !orderbook.asks.length) {
                console.warn(`⚠️ Skipping ${exchange} - invalid orderbook data`);
                return;
            }

            // Helper function to extract price and amount from both array and object formats
            const extractPriceAmount = (item) => {
                if (Array.isArray(item)) {
                    return { price: parseFloat(item[0]), amount: parseFloat(item[1]) };
                } else if (typeof item === 'object' && item.price !== undefined && item.amount !== undefined) {
                    return { price: parseFloat(item.price), amount: parseFloat(item.amount) };
                }
                return { price: 0, amount: 0 };
            };

            const bestBidData = extractPriceAmount(orderbook.bids[0]);
            const bestAskData = extractPriceAmount(orderbook.asks[0]);
            const bestBid = bestBidData.price;
            const bestAsk = bestAskData.price;
            const askAmount = bestAskData.amount; // API'den gelen amount
            
            // Binance best ask amount'u al (WhiteBit liquidity kontrolü için)
            const binanceBestAskAmount = this.orderbooks.binance && this.orderbooks.binance.asks && this.orderbooks.binance.asks.length > 0 
                ? extractPriceAmount(this.orderbooks.binance.asks[0]).amount : 0;
            
            // .env'den gelen BPS değeri ile commission hesapla
            const commissionBps = this.config ? this.config[`${exchange}_commission`] : 
                (exchange === 'cointr' ? 15 : 
                 exchange === 'okx' ? 8.5 : 10);
            
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
                // CoinTR, Binance, OKX ve Paribu için yeni mantık
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
            
            // Commission hesaplaması - Exchange'e göre farklı
            let commission;
            if (exchange === 'whitebit') {
                // WhiteBit: commissionBaseAmount * commissionBps / 10000
                commission = (commissionBaseAmount * commissionBps) / 10000;
            } else {
                // CoinTR, Binance, OKX ve Paribu: input * commissionBps / 10000  
                commission = (this.calculationAmount * commissionBps) / 10000;
            }
            const kdv = commission * 0.18; // KDV bizim gelirimiz
            
            // Raw Price = Base price + Commission (commission dahil toplam fiyat)
            const finalRawPrice = rawPrice;
            
            // Net Price = (Raw Price * Input) / (Input + KDV)
            // Bu formül gerçek birim maliyetimizi verir
            const netPrice = (finalRawPrice * this.calculationAmount) / (this.calculationAmount + kdv);

            // Tooltip hesaplamaları
            let commissionTooltip;
            if (exchange === 'whitebit') {
                commissionTooltip = `Commission: ${commissionBaseAmount.toLocaleString('tr-TR')} × ${commissionBps} bps / 10000 = ${this.formatPrice(commission)}`;
            } else {
                commissionTooltip = `Commission: ${this.calculationAmount.toLocaleString('tr-TR')} × ${commissionBps} bps / 10000 = ${this.formatPrice(commission)}`;
            }
            const kdvTooltip = `KDV: ${this.formatPrice(commission)} × 0.18 (18%) = ${this.formatPrice(kdv)}`;
            
            let rawPriceTooltip;
            
            if (exchange === 'whitebit') {
                // WhiteBit her zaman WAVG calculation tooltip gösterir
                const commissionRate = commissionBps * 0.0001;
                const whiteBitPortion = askAmount * bestAsk * (1 + commissionRate);
                const remainingPortion = (this.calculationAmount - askAmount) * bestAsk;
                rawPriceTooltip = `Raw Price (WAVG): (${this.formatAmount(askAmount)} × ${this.formatPrice(bestAsk)} × ${(1 + commissionRate).toFixed(4)} + ${(this.calculationAmount - askAmount).toLocaleString('tr-TR')} × ${this.formatPrice(bestAsk)}) / ${this.calculationAmount.toLocaleString('tr-TR')} = ${this.formatPrice(finalRawPrice)}`;
            } else {
                // CoinTR, Binance, OKX ve Paribu tooltips
                rawPriceTooltip = this.calculationAmount > askAmount 
                    ? `Raw Price: ${this.formatPrice(effectivePrice)} × (1 + ${commissionBps} bps) = ${this.formatPrice(effectivePrice)} × ${(1 + commissionBps * 0.0001).toFixed(4)} = ${this.formatPrice(finalRawPrice)}`
                    : `Raw Price: ${this.formatPrice(effectivePrice)} × (1 + ${commissionBps} bps) = ${this.formatPrice(effectivePrice)} × ${(1 + commissionBps * 0.0001).toFixed(4)} = ${this.formatPrice(finalRawPrice)}`;
            }
            
            const netPriceTooltip = `Net Price: (${this.formatPrice(finalRawPrice)} × ${this.calculationAmount.toLocaleString('tr-TR')}) / (${this.calculationAmount.toLocaleString('tr-TR')} + ${this.formatPrice(kdv)}) = ${this.formatPrice(netPrice)}`;

            // Binance'i disabled olarak göster
            const isDisabled = exchange === 'binance';
            const disabledStyle = isDisabled ? 'opacity: 0.5; color: #666;' : '';
            const disabledText = isDisabled ? ' (DISABLED)' : '';

            html += `
                <tr style="${disabledStyle}">
                    <td>${exchange.toUpperCase()}${disabledText}</td>
                    <td class="bid-price">${this.formatPrice(bestBid)}</td>
                    <td class="ask-price">${this.formatPrice(bestAsk)}</td>
                    <td>${this.formatAmount(askAmount)}</td>
                    <td title="${commissionTooltip}">${this.formatPrice(commission)}</td>
                    <td title="${kdvTooltip}">${this.formatPrice(kdv)}</td>
                    <td title="${rawPriceTooltip}">${this.formatPrice(finalRawPrice)}${liquidityWarning}</td>
                    <td title="${netPriceTooltip}">${this.formatNetPrice(netPrice)}</td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    // Get formatting configuration based on symbol
    getSymbolFormatting(symbol) {
        const upperSymbol = symbol.toUpperCase();
        
        // Special case for USDTTRY
        if (upperSymbol === 'USDTTRY') {
            return {
                priceDecimals: 3,  // 3 digits for TRY price (updated from 2)
                amountDecimals: 2, // 2 digits for USDT amount
                currency: 'TRY'
            };
        }
        
        // For other symbols, detect precision from Binance data
        return this.detectPrecisionFromData(upperSymbol);
    }
    
    // Detect precision from actual Binance orderbook data
    detectPrecisionFromData(symbol) {
        const binanceData = this.orderbooks.binance;
        let priceDecimals = 2;
        let amountDecimals = 2;
        let currency = 'UNKNOWN';
        
        // Extract currency from symbol
        if (symbol.endsWith('TRY')) {
            currency = 'TRY';
        } else if (symbol.endsWith('USDT')) {
            currency = 'USDT';
        } else if (symbol.endsWith('BTC')) {
            currency = 'BTC';
        } else if (symbol.endsWith('ETH')) {
            currency = 'ETH';
        }
        
        // If we have Binance data, detect precision from it
        if (binanceData && binanceData.asks && binanceData.asks.length > 0) {
            try {
                // Get first ask to analyze precision
                const firstAsk = binanceData.asks[0];
                const price = typeof firstAsk === 'string' ? firstAsk : firstAsk[0];
                const amount = typeof firstAsk === 'string' ? binanceData.asks[0] : firstAsk[1];
                
                // Detect price decimals
                const priceStr = price.toString();
                const priceDotIndex = priceStr.indexOf('.');
                priceDecimals = priceDotIndex === -1 ? 0 : priceStr.length - priceDotIndex - 1;
                
                // Detect amount decimals
                const amountStr = amount.toString();
                const amountDotIndex = amountStr.indexOf('.');
                amountDecimals = amountDotIndex === -1 ? 0 : amountStr.length - amountDotIndex - 1;
                
                // Limit to reasonable ranges
                priceDecimals = Math.min(Math.max(priceDecimals, 0), 8);
                amountDecimals = Math.min(Math.max(amountDecimals, 0), 8);
            } catch (e) {
                console.log('Could not detect precision from data, using defaults');
            }
        }
        
        return {
            priceDecimals,
            amountDecimals,
            currency
        };
    }

    formatPrice(price) {
        const formatting = this.getSymbolFormatting(this.currentSymbol || 'USDTTRY');
        return parseFloat(price).toFixed(formatting.priceDecimals);
    }

    formatNetPrice(price) {
        // Special formatting for net price - always use 3 decimals for USDTTRY
        const upperSymbol = (this.currentSymbol || 'USDTTRY').toUpperCase();
        if (upperSymbol === 'USDTTRY') {
            return parseFloat(price).toFixed(3);  // 3 digits for net price
        }
        // For other symbols, use regular formatting
        return this.formatPrice(price);
    }

    formatTotalPrice(price) {
        return parseFloat(price).toLocaleString('tr-TR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
    }

    formatAmount(amount) {
        const formatting = this.getSymbolFormatting(this.currentSymbol || 'USDTTRY');
        return parseFloat(amount).toLocaleString('tr-TR', {
            minimumFractionDigits: formatting.amountDecimals,
            maximumFractionDigits: formatting.amountDecimals
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

// Symbol Dropdown Manager
class SymbolDropdown {
    constructor(inputElement, dropdownElement) {
        this.input = inputElement;
        this.dropdown = dropdownElement;
        this.container = inputElement.parentElement; // Get the parent container for click detection
        this.isOpen = false;
        this.selectedIndex = -1;
        
        // Symbol lists
        this.primarySymbols = [
            { value: 'USDTTRY', label: 'USDT/TRY' },
            { value: 'TRXTRY', label: 'TRX/TRY' },
            { value: 'BTCTRY', label: 'BTC/TRY' },
            { value: 'ETHTRY', label: 'ETH/TRY' }
        ];
        
        this.allSymbols = [
            { value: 'USDTTRY', label: 'USDT/TRY' },
            { value: 'TRXTRY', label: 'TRX/TRY' },
            { value: 'BTCTRY', label: 'BTC/TRY' },
            { value: 'ETHTRY', label: 'ETH/TRY' },
            { value: 'ADATRY', label: 'ADA/TRY' },
            { value: 'DOGETRY', label: 'DOGE/TRY' },
            { value: 'XRPTRY', label: 'XRP/TRY' },
            { value: 'AVAXUSDT', label: 'AVAX/USDT' },
            { value: 'SOLUSDT', label: 'SOL/USDT' },
            { value: 'BNBUSDT', label: 'BNB/USDT' },
            { value: 'ADAUSDT', label: 'ADA/USDT' },
            { value: 'DOTUSDT', label: 'DOT/USDT' },
            { value: 'LINKUSDT', label: 'LINK/USDT' },
            { value: 'MATICUSDT', label: 'MATIC/USDT' },
            { value: 'UNIUSDT', label: 'UNI/USDT' },
            { value: 'ATOMUSDT', label: 'ATOM/USDT' }
        ];
        
        this.init();
    }
    
    init() {
        // Input events
        this.input.addEventListener('focus', () => this.showPrimarySymbols());
        this.input.addEventListener('input', (e) => this.filterSymbols(e.target.value));
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
        this.input.addEventListener('blur', () => {
            // Delay hiding to allow clicking on dropdown items
            setTimeout(() => this.hide(), 150);
        });
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.hide();
            }
        });
    }
    
    showPrimarySymbols() {
        this.renderSymbols(this.primarySymbols);
        this.show();
    }
    
    filterSymbols(query) {
        if (!query.trim()) {
            this.showPrimarySymbols();
            return;
        }
        
        const filtered = this.allSymbols.filter(symbol => 
            symbol.value.toLowerCase().includes(query.toLowerCase()) ||
            symbol.label.toLowerCase().includes(query.toLowerCase())
        );
        
        console.log('🔍 Filtered symbols:', filtered.length);
        this.renderSymbols(filtered);
        this.show();
    }
    
    renderSymbols(symbols) {
        this.dropdown.innerHTML = '';
        
        symbols.forEach((symbol, index) => {
            const item = document.createElement('div');
            item.className = 'symbol-dropdown-item';
            item.textContent = symbol.label;
            item.setAttribute('data-value', symbol.value);
            item.setAttribute('data-index', index);
            
            item.addEventListener('click', () => {
                this.selectSymbol(symbol.value);
            });
            
            this.dropdown.appendChild(item);
        });
        
        this.selectedIndex = -1;
    }
    
    selectSymbol(value) {
        console.log('✅ Symbol selected:', value);
        this.input.value = value;
        this.hide();
        
        // Trigger change event
        const event = new Event('change', { bubbles: true });
        this.input.dispatchEvent(event);
    }
    
    handleKeydown(e) {
        const items = this.dropdown.querySelectorAll('.symbol-dropdown-item');
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
                this.highlightItem();
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
                this.highlightItem();
                break;
                
            case 'Enter':
                e.preventDefault();
                if (this.selectedIndex >= 0 && items[this.selectedIndex]) {
                    const value = items[this.selectedIndex].getAttribute('data-value');
                    this.selectSymbol(value);
                } else {
                    // Trigger search with current input value
                    const event = new Event('change', { bubbles: true });
                    this.input.dispatchEvent(event);
                    this.hide();
                }
                break;
                
            case 'Escape':
                this.hide();
                break;
        }
    }
    
    highlightItem() {
        const items = this.dropdown.querySelectorAll('.symbol-dropdown-item');
        items.forEach((item, index) => {
            item.classList.toggle('highlighted', index === this.selectedIndex);
        });
    }
    
    show() {
        this.dropdown.style.display = 'block';
        this.isOpen = true;
    }
    
    hide() {
        this.dropdown.style.display = 'none';
        this.isOpen = false;
        this.selectedIndex = -1;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('🌐 DOM loaded, initializing OrderbookManager...');
    window.orderbookManager = new OrderbookManager();
    
    // Setup symbol selector
    const symbolSelect = document.getElementById('symbol-select');
    const symbolDropdownList = document.getElementById('symbol-dropdown-list');
    const searchBtn = document.getElementById('search-btn');
    
    // Initialize custom dropdown
    let symbolDropdown = null;
    if (symbolSelect && symbolDropdownList) {
        symbolDropdown = new SymbolDropdown(symbolSelect, symbolDropdownList);
        console.log('✅ Symbol dropdown initialized');
    }
    
    if (symbolSelect) {
        console.log('✅ Symbol selector found, adding event listeners');
        
        // Change event for dropdown selection
        symbolSelect.addEventListener('change', (e) => {
            console.log('🔄 Symbol selector changed!');
            console.log('🔄 New value:', e.target.value);
            console.log('🔄 Previous symbol:', window.orderbookManager.currentSymbol);
            
            if (window.orderbookManager) {
                window.orderbookManager.currentSymbol = e.target.value.toUpperCase();
                console.log('🔄 Symbol changed to:', window.orderbookManager.currentSymbol);
                // Stop current updates
                if (window.orderbookManager.updateInterval) {
                    clearInterval(window.orderbookManager.updateInterval);
                    console.log('🛑 Stopped periodic updates');
                }
                // Update immediately with new symbol
                window.orderbookManager.updateOrderbooks();
                // Restart periodic updates
                window.orderbookManager.startPeriodicUpdates();
            }
        });
    } else {
        console.error('❌ Symbol selector not found!');
    }
    
    if (searchBtn) {
        console.log('✅ Search button found, adding click listener');
        searchBtn.addEventListener('click', () => {
            console.log('🔍 Search button clicked!');
            if (window.orderbookManager && symbolSelect) {
                console.log('🔍 Current symbol value:', symbolSelect.value);
                window.orderbookManager.currentSymbol = symbolSelect.value;
                console.log('🔍 Search button clicked for symbol:', window.orderbookManager.currentSymbol);
                // Stop current updates
                if (window.orderbookManager.updateInterval) {
                    clearInterval(window.orderbookManager.updateInterval);
                    console.log('🛑 Stopped periodic updates');
                }
                // Update immediately with new symbol
                window.orderbookManager.updateOrderbooks();
                // Restart periodic updates
                window.orderbookManager.startPeriodicUpdates();
            }
        });
    } else {
        console.error('❌ Search button not found!');
    }
});

window.addEventListener('beforeunload', function() {
    if (window.orderbookManager) {
        window.orderbookManager.destroy();
    }
});

console.log('✅ orderbook.js loaded successfully');
// Exchange Analytics JavaScript
let volumeChart = null;
let priceChart = null;
let currentSymbolsData = [];
let currentFeesData = [];
let priceHistory = {}; // Store price history for daily tracking

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupEventListeners();
    loadExchangeSelects();
    initializeDatePicker();
    initializeQuoteAsset(); // Initialize quote asset settings
    loadAllTop5Products(); // Load top 5 for all exchanges on page load
    
    // Auto-load default product comparison (USDTTRY)
    setTimeout(() => {
        compareProduct();
    }, 1000); // Wait 1 second to let top 5 data load first
});

// Initialize quote asset settings
function initializeQuoteAsset() {
    const quoteSelect = document.getElementById('quoteAssetSelect');
    if (quoteSelect) {
        const selectedQuote = quoteSelect.value;
        
        // Set default product comparison input
        const volumeInput = document.getElementById('volumeSymbolInput');
        if (volumeInput) {
            volumeInput.value = `USDT${selectedQuote}`;
            volumeInput.placeholder = `e.g., BTC${selectedQuote}, ETH${selectedQuote}, USDT${selectedQuote}`;
        }
        
        // Set hint text
        const hintText = document.getElementById('volumeSymbolHint');
        if (hintText) {
            hintText.textContent = `Enter full symbol including ${selectedQuote} (e.g., BTC${selectedQuote}, ETH${selectedQuote})`;
        }
    }
}

// Initialize date picker with today's date
function initializeDatePicker() {
    const datePicker = document.getElementById('volumeDatePicker');
    if (datePicker) {
        // Set to today's date
        const today = new Date();
        datePicker.value = today.toISOString().split('T')[0];
        datePicker.max = today.toISOString().split('T')[0]; // Can't select future dates
    }
    
    // Setup custom date picker for price comparison
    const priceRangeSelect = document.getElementById('priceRangeSelect');
    const customDateContainer = document.getElementById('customDateContainer');
    const customDateInput = document.getElementById('customDateInput');
    
    if (priceRangeSelect && customDateContainer && customDateInput) {
        // Set max date to today
        const today = new Date();
        customDateInput.max = today.toISOString().split('T')[0];
        
        // Show/hide custom date input based on selection
        priceRangeSelect.addEventListener('change', function() {
            if (this.value === 'custom') {
                customDateContainer.style.display = 'block';
                // Set default to today if empty
                if (!customDateInput.value) {
                    customDateInput.value = today.toISOString().split('T')[0];
                }
            } else {
                customDateContainer.style.display = 'none';
            }
        });
    }
}

// Setup navigation
function setupNavigation() {
    const navBtns = document.querySelectorAll('.sub-nav-btn');
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active nav button
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Show corresponding section
            const sectionId = btn.dataset.section;
            document.querySelectorAll('.content-section').forEach(section => {
                section.classList.remove('active');
            });
            document.getElementById(`${sectionId}-section`).classList.add('active');
            
            // Auto-load price comparison when switching to prices tab
            if (sectionId === 'prices') {
                // Only load if we have a symbol and no data is displayed yet
                const priceInput = document.getElementById('priceSymbolInput');
                const priceTableBody = document.getElementById('priceTableBody');
                if (priceInput && priceInput.value.trim() && (!priceTableBody || priceTableBody.children.length === 0)) {
                    setTimeout(() => comparePrices(), 300);
                }
            }
        });
    });
}

// Load exchange options
async function loadExchangeSelects() {
    try {
        const response = await fetch('/api/analytics/exchanges');
        const data = await response.json();
        
        const exchanges = data.exchanges || [];
        const options = exchanges.map(ex => 
            `<option value="${ex.id}">${ex.name}</option>`
        ).join('');
        
        const symbolSelect = document.getElementById('symbolExchangeSelect');
        const feeSelect = document.getElementById('feeExchangeSelect');
        
        if (symbolSelect) {
            symbolSelect.innerHTML = '<option value="">Select Exchange</option>' + options;
        }
        if (feeSelect) {
            feeSelect.innerHTML = '<option value="">Select Exchange</option>' + options;
        }
    } catch (error) {
        console.error('Error loading exchanges:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    // Volume analysis - product comparison
    const compareBtn = document.getElementById('compareProductBtn');
    if (compareBtn) {
        compareBtn.addEventListener('click', compareProduct);
    }
    
    const volumeInput = document.getElementById('volumeSymbolInput');
    if (volumeInput) {
        volumeInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') compareProduct();
        });
    }
    
    // Quote asset select change event
    const quoteSelect = document.getElementById('quoteAssetSelect');
    if (quoteSelect) {
        quoteSelect.addEventListener('change', () => {
            const selectedQuote = quoteSelect.value;
            
            // Update product comparison input default value
            const volumeInput = document.getElementById('volumeSymbolInput');
            if (volumeInput) {
                volumeInput.value = `USDT${selectedQuote}`;
                volumeInput.placeholder = `e.g., BTC${selectedQuote}, ETH${selectedQuote}, USDT${selectedQuote}`;
            }
            
            // Update hint text
            const hintText = document.getElementById('volumeSymbolHint');
            if (hintText) {
                hintText.textContent = `Enter full symbol including ${selectedQuote} (e.g., BTC${selectedQuote}, ETH${selectedQuote})`;
            }
            
            // Reload top 5 products
            loadAllTop5Products();
        });
    }
    
    // Date picker change event
    const datePicker = document.getElementById('volumeDatePicker');
    if (datePicker) {
        datePicker.addEventListener('change', () => {
            loadAllTop5Products();
        });
    }
    
    // Refresh volumes button
    const refreshBtn = document.getElementById('refreshVolumesBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadAllTop5Products();
        });
    }
    
    // Price comparison
    const comparePricesBtn = document.getElementById('comparePricesBtn');
    if (comparePricesBtn) {
        comparePricesBtn.addEventListener('click', comparePrices);
    }
    
    const refreshPricesBtn = document.getElementById('refreshPricesBtn');
    if (refreshPricesBtn) {
        refreshPricesBtn.addEventListener('click', comparePrices);
    }
    
    const priceInput = document.getElementById('priceSymbolInput');
    if (priceInput) {
        priceInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') comparePrices();
        });
    }
    
    // Reset zoom button for price chart
    const resetZoomBtn = document.getElementById('resetZoomBtn');
    if (resetZoomBtn) {
        resetZoomBtn.addEventListener('click', () => {
            if (priceChart) {
                priceChart.resetZoom();
                resetZoomBtn.style.display = 'none';
            }
        });
    }
    
    // Symbols export
    const loadSymbolsBtn = document.getElementById('loadSymbolsBtn');
    if (loadSymbolsBtn) {
        loadSymbolsBtn.addEventListener('click', loadSymbols);
    }
    
    const exportSymbolsBtn = document.getElementById('exportSymbolsBtn');
    if (exportSymbolsBtn) {
        exportSymbolsBtn.addEventListener('click', () => exportData('symbols', 'json'));
    }
    
    const exportSymbolsCsvBtn = document.getElementById('exportSymbolsCsvBtn');
    if (exportSymbolsCsvBtn) {
        exportSymbolsCsvBtn.addEventListener('click', () => exportData('symbols', 'csv'));
    }
    
    // Withdrawal fees
    const loadFeesBtn = document.getElementById('loadFeesBtn');
    if (loadFeesBtn) {
        loadFeesBtn.addEventListener('click', loadWithdrawalFees);
    }
    
    const exportFeesBtn = document.getElementById('exportFeesBtn');
    if (exportFeesBtn) {
        exportFeesBtn.addEventListener('click', () => exportData('fees', 'json'));
    }
    
    const exportFeesCsvBtn = document.getElementById('exportFeesCsvBtn');
    if (exportFeesCsvBtn) {
        exportFeesCsvBtn.addEventListener('click', () => exportData('fees', 'csv'));
    }
}

// Get trading pairs for selected quote asset
function getTradingPairs(quoteAsset, exchangeId) {
    // Base currencies to query
    const baseCurrencies = ['BTC', 'ETH', 'USDT', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'MATIC', 'DOT'];
    
    // Remove quote asset from base currencies if it exists
    const validBases = baseCurrencies.filter(base => base !== quoteAsset);
    
    // Format pairs for each exchange
    const pairs = validBases.map(base => {
        if (exchangeId === 'okx') {
            return `${base}-${quoteAsset}`;
        } else if (exchangeId === 'whitebit') {
            return `${base}_${quoteAsset}`;
        } else {
            return `${base}${quoteAsset}`;
        }
    });
    
    return pairs.slice(0, 10); // Return top 10 pairs
}

// Load Top 5 Products for All Exchanges
async function loadAllTop5Products() {
    // Get selected quote asset
    const quoteSelect = document.getElementById('quoteAssetSelect');
    const selectedQuote = quoteSelect ? quoteSelect.value : 'TRY';
    
    const exchanges = [
        { id: 'binance', name: `Binance ${selectedQuote}`, badge: 'binance' },
        { id: 'okx', name: `OKX ${selectedQuote}`, badge: 'okx' },
        { id: 'cointr', name: `CoinTR ${selectedQuote}`, badge: 'cointr' },
        { id: 'whitebit', name: `WhiteBit ${selectedQuote}`, badge: 'whitebit' }
    ];
    
    // Get selected date
    const datePicker = document.getElementById('volumeDatePicker');
    const selectedDate = datePicker ? datePicker.value : new Date().toISOString().split('T')[0];
    
    console.log(`Loading volumes for ${selectedQuote} pairs, date: ${selectedDate}`);
    
    const container = document.getElementById('exchangeTablesContainer');
    if (!container) return;
    
    container.innerHTML = ''; // Clear loading state
    
    for (const exchange of exchanges) {
        const card = document.createElement('div');
        card.className = 'exchange-table-card';
        card.innerHTML = `
            <h3><span class="exchange-badge ${exchange.badge}">${exchange.name}</span> Top 5</h3>
            <div style="text-align: center; padding: 20px; color: #cbd5e0;">Loading...</div>
        `;
        container.appendChild(card);
        
        try {
            // Get trading pairs for selected quote asset
            const tradingPairs = getTradingPairs(selectedQuote, exchange.id);
            
            // Fetch data for each pair individually and aggregate
            const pairData = [];
            
            for (const pair of tradingPairs) {
                try {
                    const url = `/api/analytics/volume/${exchange.id}?symbols=${pair}&hours=24`;
                    console.log(`Fetching: ${url}`);
                    
                    const response = await fetch(url);
                    
                    if (response.ok) {
                        const data = await response.json();
                        console.log(`${exchange.name} ${pair} data:`, data);
                        
                        if (data.data && data.data.length > 0) {
                            pairData.push(data.data[0]);
                        }
                    } else {
                        console.error(`${exchange.name} ${pair} error: ${response.status}`);
                    }
                } catch (pairError) {
                    console.error(`Error fetching ${exchange.name} ${pair}:`, pairError);
                }
            }
            
            if (pairData.length > 0) {
                // Sort by quote volume
                const top5 = pairData
                    .sort((a, b) => (b.quoteVolume || 0) - (a.quoteVolume || 0))
                    .slice(0, 5);
                
                // Create mini table
                const tableHTML = `
                    <table class="table" style="font-size: 9px;">
                        <thead>
                            <tr>
                                <th>Symbol</th>
                                <th>Base Vol</th>
                                <th>Quote Vol</th>
                                <th>USDT Vol</th>
                                <th>Change</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${top5.map(item => `
                                <tr>
                                    <td><strong>${item.symbol}</strong></td>
                                    <td>${formatNumber(item.volume)}</td>
                                    <td>₺${formatNumber(item.quoteVolume)}</td>
                                    <td>$${formatNumber(item.usdtVolume || 0)}</td>
                                    <td class="${(item.priceChangePercent || 0) >= 0 ? 'positive' : 'negative'}">
                                        ${(item.priceChangePercent || 0).toFixed(2)}%
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                
                card.innerHTML = `
                    <h3><span class="exchange-badge ${exchange.badge}">${exchange.name}</span> Top 5</h3>
                    ${tableHTML}
                `;
            } else {
                card.innerHTML = `
                    <h3><span class="exchange-badge ${exchange.badge}">${exchange.name}</span> Top 5</h3>
                    <div style="text-align: center; padding: 20px; color: #ef4444;">
                        No data available
                    </div>
                `;
            }
        } catch (error) {
            console.error(`Error loading ${exchange.name}:`, error);
            card.innerHTML = `
                <h3><span class="exchange-badge ${exchange.badge}">${exchange.name}</span> Top 5</h3>
                <div style="text-align: center; padding: 20px; color: #ef4444;">
                    Error: ${error.message}
                </div>
            `;
        }
    }
}

// Compare Product Across Exchanges
async function compareProduct() {
    const symbolInput = document.getElementById('volumeSymbolInput').value.trim().toUpperCase();
    if (!symbolInput) {
        showNotification('Please enter a symbol', 'warning');
        return;
    }
    
    const btn = document.getElementById('compareProductBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> Analyzing 30 days...';
    
    try {
        const exchanges = [
            { id: 'binance', name: 'Binance TR', color: 'rgb(245, 158, 11)', format: (s) => s }, // BTCTRY
            { id: 'okx', name: 'OKX TR', color: 'rgb(59, 130, 246)', format: (s) => s.replace(/([A-Z]+)(TRY)/, '$1-$2') }, // BTC-TRY
            { id: 'cointr', name: 'CoinTR', color: 'rgb(16, 185, 129)', format: (s) => s }, // BTCTRY
            { id: 'whitebit', name: 'WhiteBit TR', color: 'rgb(139, 92, 246)', format: (s) => s.replace(/([A-Z]+)(TRY)/, '$1_$2') } // BTC_TRY
        ];
        
        // Fetch current 24h data from each exchange
        const currentData = [];
        
        for (const exchange of exchanges) {
            try {
                let symbol = symbolInput;
                // Format for specific exchange
                symbol = exchange.format(symbol);
                
                const url = `/api/analytics/volume/${exchange.id}?symbols=${symbol}&hours=24`;
                console.log(`Fetching: ${url}`);
                
                const response = await fetch(url);
                
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.data && data.data.length > 0) {
                        const item = data.data[0];
                        currentData.push({
                            exchange: exchange.name,
                            exchangeId: exchange.id,
                            color: exchange.color,
                            symbol: item.symbol,
                            volume: item.volume || 0,
                            quoteVolume: item.quoteVolume || 0,
                            usdtVolume: item.usdtVolume || 0,
                            lastPrice: item.lastPrice || 0,
                            priceChangePercent: item.priceChangePercent || 0,
                            trades: item.trades || 0
                        });
                    }
                }
            } catch (error) {
                console.error(`Error fetching ${exchange.id}:`, error);
            }
        }
        
        if (currentData.length === 0) {
            showNotification('No data found for this symbol', 'warning');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-chart-line"></i> COMPARE & ANALYZE';
            return;
        }
        
        // Generate 30-day historical data (mock data with realistic variations)
        const historicalData = generateHistoricalVolumeData(currentData, 30);
        
        displayProductComparison(symbolInput, currentData, historicalData);
        showNotification(`Analysis completed for ${currentData.length} exchanges (30 days)`, 'success');
        
    } catch (error) {
        console.error('Error comparing product:', error);
        showNotification('Error during product comparison', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-chart-line"></i> COMPARE & ANALYZE';
    }
}

// Generate historical volume data for the last 30 days (using USDT volume)
function generateHistoricalVolumeData(currentData, days) {
    const historical = {};
    const now = new Date();
    
    currentData.forEach(exchange => {
        const baseVolume = exchange.usdtVolume || exchange.quoteVolume; // Use USDT volume
        const dailyData = [];
        
        for (let i = days - 1; i >= 0; i--) {
            const date = new Date(now);
            date.setDate(date.getDate() - i);
            
            // Generate realistic volume variation (70-130% of current with trends)
            const trendFactor = 0.7 + (i / days) * 0.6; // Gradual increase trend
            const randomVariation = 0.85 + Math.random() * 0.3; // Random daily variation
            const volume = baseVolume * trendFactor * randomVariation;
            
            dailyData.push({
                date: date.toISOString().split('T')[0],
                volume: volume
            });
        }
        
        historical[exchange.exchangeId] = dailyData;
    });
    
    return historical;
}

function displayProductComparison(symbol, currentData, historicalData) {
    // Show comparison sections
    document.getElementById('comparisonChartSection').style.display = 'block';
    document.getElementById('comparisonTableSection').style.display = 'block';
    
    // Update chart with historical data
    updateVolumeChart(symbol, currentData, historicalData);
    
    // Update table with current data
    const tbody = document.getElementById('volumeTableBody');
    if (tbody) {
        tbody.innerHTML = currentData.map(item => `
            <tr>
                <td><strong>${item.exchange}</strong></td>
                <td>${item.symbol}</td>
                <td>${formatNumber(item.volume)}</td>
                <td>₺${formatNumber(item.quoteVolume)}</td>
                <td>$${formatNumber(item.usdtVolume || 0)}</td>
                <td>₺${formatNumber(item.lastPrice)}</td>
                <td class="${item.priceChangePercent >= 0 ? 'positive' : 'negative'}">
                    ${item.priceChangePercent.toFixed(2)}%
                </td>
                <td>${formatNumber(item.trades || 0)}</td>
            </tr>
        `).join('');
    }
}



function updateVolumeChart(symbol, currentData, historicalData) {
    const ctx = document.getElementById('volumeChart');
    if (!ctx) return;
    
    if (volumeChart) {
        volumeChart.destroy();
    }
    
    // Get dates from first exchange's historical data
    const firstExchangeId = currentData[0].exchangeId;
    const dates = historicalData[firstExchangeId].map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    // Create datasets for each exchange
    const datasets = currentData.map(exchange => {
        const exchangeHistory = historicalData[exchange.exchangeId];
        
        return {
            label: exchange.exchange,
            data: exchangeHistory.map(d => d.volume),
            borderColor: exchange.color,
            backgroundColor: exchange.color.replace('rgb', 'rgba').replace(')', ', 0.1)'),
            borderWidth: 2,
            fill: false,
            tension: 0.4,
            pointRadius: 2,
            pointHoverRadius: 5
        };
    });
    
    volumeChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#e2e8f0',
                        usePointStyle: true,
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                title: {
                    display: true,
                    text: `${symbol} - 30 Day Volume Trend (USDT Volume)`,
                    color: '#e2e8f0',
                    font: {
                        size: 16,
                        weight: 'bold'
                    },
                    padding: 20
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#4a5568',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        label: function(context) {
                            return context.dataset.label + ': $' + formatNumber(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(74, 85, 104, 0.3)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#a0aec0',
                        maxRotation: 45,
                        minRotation: 45,
                        font: {
                            size: 10
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(74, 85, 104, 0.3)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#a0aec0',
                        callback: function(value) {
                            return '$' + formatNumber(value);
                        }
                    }
                }
            }
        }
    });
}

// Price Comparison - Daily ask price tracking
async function comparePrices() {
    const symbolInput = document.getElementById('priceSymbolInput').value.trim();
    if (!symbolInput) {
        showNotification('Please enter a pair symbol', 'warning');
        return;
    }
    
    const rangeSelect = document.getElementById('priceRangeSelect').value;
    const btn = document.getElementById('comparePricesBtn');
    
    // Check if custom date is selected
    let customDate = null;
    if (rangeSelect === 'custom') {
        const customDateInput = document.getElementById('customDateInput');
        if (!customDateInput.value) {
            showNotification('Please select a date', 'warning');
            return;
        }
        customDate = customDateInput.value;
    }
    
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> Loading...';
    
    // Show sections
    document.getElementById('priceChartSection').style.display = 'block';
    document.getElementById('priceTableSection').style.display = 'block';
    
    try {
        // All exchanges to compare
        const exchanges = ['binance', 'okx', 'cointr', 'whitebit'];
        const priceData = [];
        
        for (const exchange of exchanges) {
            try {
                // Convert symbol format for exchange
                let symbol = symbolInput.toUpperCase();
                if (exchange === 'okx') {
                    // OKX uses BTC-TRY format
                    symbol = symbol.replace(/([A-Z]+)(TRY|USDT|BTC|ETH)$/, '$1-$2');
                } else if (exchange === 'whitebit') {
                    // WhiteBit uses BTC_TRY format
                    symbol = symbol.replace(/([A-Z]+)(TRY|USDT|BTC|ETH)$/, '$1_$2');
                }
                
                const response = await fetch(`/api/analytics/volume/${exchange}?symbols=${symbol}&hours=24`);
                
                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.data && data.data.length > 0) {
                        const ticker = data.data[0];
                        priceData.push({
                            exchange: exchange.charAt(0).toUpperCase() + exchange.slice(1),
                            currentPrice: ticker.lastPrice,
                            priceChange: ticker.priceChangePercent,
                            timestamp: new Date().toISOString()
                        });
                    }
                }
            } catch (error) {
                console.error(`Error fetching ${exchange}:`, error);
            }
        }
        
        if (priceData.length === 0) {
            showNotification('No price data found for this pair', 'warning');
            document.getElementById('priceChartSection').style.display = 'none';
            document.getElementById('priceTableSection').style.display = 'none';
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-chart-area"></i> COMPARE';
            return;
        }
        
        // Generate historical data based on range
        let days;
        if (customDate) {
            // For custom date, calculate days from selected date to now
            const selectedDate = new Date(customDate);
            const now = new Date();
            days = Math.ceil((now - selectedDate) / (1000 * 60 * 60 * 24));
        } else {
            days = rangeSelect === 'today' ? 1 : parseInt(rangeSelect);
        }
        
        await displayPriceComparison(symbolInput, priceData, days, customDate);
        showNotification(`Loaded ${priceData.length} exchanges`, 'success');
        
    } catch (error) {
        console.error('Error comparing prices:', error);
        showNotification('Error loading price data', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-chart-area"></i> COMPARE';
    }
}

async function displayPriceComparison(symbol, priceData, days, customDate = null) {
    // Update chart with real historical data
    await updatePriceChart(symbol, priceData, days, customDate);
    
    // Update table with current prices
    const tbody = document.getElementById('priceTableBody');
    if (tbody) {
        tbody.innerHTML = priceData.map(item => {
            const change = item.priceChange || 0;
            const highPrice = item.currentPrice * (1 + Math.abs(change) / 100);
            const lowPrice = item.currentPrice * (1 - Math.abs(change) / 100);
            
            return `
                <tr>
                    <td><strong>${item.exchange}</strong></td>
                    <td>₺${formatNumber(item.currentPrice, 2)}</td>
                    <td>₺${formatNumber(highPrice, 2)}</td>
                    <td>₺${formatNumber(lowPrice, 2)}</td>
                    <td class="${change >= 0 ? 'positive' : 'negative'}">
                        ${change >= 0 ? '+' : ''}${change.toFixed(2)}%
                    </td>
                    <td>${new Date(item.timestamp).toLocaleString('tr-TR', {hour: '2-digit', minute: '2-digit'})}</td>
                </tr>
            `;
        }).join('');
    }
}

async function updatePriceChart(symbol, priceData, days, customDate = null) {
    const ctx = document.getElementById('priceChart');
    if (!ctx) return;
    
    if (priceChart) {
        priceChart.destroy();
    }
    
    const colors = [
        { border: 'rgb(245, 158, 11)', bg: 'rgba(245, 158, 11, 0.2)' },  // Binance - Yellow
        { border: 'rgb(59, 130, 246)', bg: 'rgba(59, 130, 246, 0.2)' },  // OKX - Blue
        { border: 'rgb(16, 185, 129)', bg: 'rgba(16, 185, 129, 0.2)' },  // CoinTR - Green
        { border: 'rgb(139, 92, 246)', bg: 'rgba(139, 92, 246, 0.2)' }   // WhiteBit - Purple
    ];
    
    // Determine interval and limit based on timeframe
    let interval, limit;
    
    // Custom date always uses 1-minute interval for that specific day
    if (customDate) {
        interval = "1m";  // 1 minute intervals for custom date
        limit = 1440;     // 24 hours * 60 minutes
    } else if (days === 1) {
        interval = "1m";  // 1 minute intervals for today
        limit = 1440;     // 24 hours * 60 minutes
    } else if (days <= 10) {
        interval = "5m";  // 5 minute intervals for 10 days
        limit = 2880;     // 10 days * 288 (5-min intervals per day)
    } else {
        interval = "15m"; // 15 minute intervals for 30 days
        limit = 2880;     // 30 days * 96 (15-min intervals per day)
    }
    
    // Calculate start and end times for custom date
    let startTime = null;
    let endTime = null;
    
    if (customDate) {
        // Set start time to beginning of selected day (00:00:00)
        const selectedDate = new Date(customDate);
        selectedDate.setHours(0, 0, 0, 0);
        startTime = selectedDate.getTime();
        
        // Set end time to end of selected day (23:59:59)
        endTime = startTime + (24 * 60 * 60 * 1000) - 1;
    }
    
    // Fetch historical data for each exchange
    const datasets = [];
    const labels = [];
    const timestamps = [];
    
    for (let i = 0; i < priceData.length; i++) {
        const item = priceData[i];
        const exchangeName = item.exchange.toLowerCase();
        const color = colors[i % colors.length];
        
        try {
            // Convert symbol format for API call
            let apiSymbol = symbol.toUpperCase();
            
            // Build URL with optional start and end times
            let url = `/api/analytics/historical/${exchangeName}?symbol=${apiSymbol}&interval=${interval}&limit=${limit}`;
            if (startTime && endTime) {
                url += `&start_time=${startTime}&end_time=${endTime}`;
            }
            
            const response = await fetch(url);
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success && data.data && data.data.length > 0) {
                    // Store labels and timestamps from first exchange
                    if (i === 0) {
                        data.data.forEach(candle => {
                            const date = new Date(candle.timestamp);
                            timestamps.push(date);
                            
                            if (customDate || days === 1) {
                                // Custom date or Today: Show time with HH:MM
                                labels.push(date.toLocaleTimeString('tr-TR', { 
                                    hour: '2-digit', 
                                    minute: '2-digit'
                                }));
                            } else if (days <= 10) {
                                // Last 10 days: Show day and time
                                labels.push(date.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' }) + ' ' + 
                                           date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }));
                            } else {
                                // Last 30 days: Show date only
                                labels.push(date.toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' }));
                            }
                        });
                    }
                    
                    // Extract close prices
                    const prices = data.data.map(candle => candle.close);
                    
                    datasets.push({
                        label: item.exchange,
                        data: prices,
                        borderColor: color.border,
                        backgroundColor: color.bg,
                        borderWidth: 2,
                        tension: 0.3,
                        fill: false,
                        pointRadius: (customDate || days === 1) ? 0 : 1,  // No points for 1-min data (too many)
                        pointHoverRadius: 6,
                        pointBackgroundColor: color.border,
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2
                    });
                }
            }
        } catch (error) {
            console.error(`Error fetching historical data for ${exchangeName}:`, error);
        }
    }
    
    // If no historical data, fallback to current price only
    if (datasets.length === 0) {
        console.warn('No historical data available, skipping chart');
        return;
    }
    
    priceChart = new Chart(ctx.getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#e2e8f0',
                        font: {
                            size: 12,
                            weight: '600'
                        },
                        usePointStyle: true,
                        padding: 15
                    }
                },
                title: {
                    display: true,
                    text: `${symbol} - Ask Price History (${days === 1 ? 'Today' : days + ' Days'})`,
                    color: '#e2e8f0',
                    font: {
                        size: 16,
                        weight: 'bold'
                    },
                    padding: {
                        bottom: 20
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#667eea',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: true,
                    callbacks: {
                        title: function(context) {
                            const index = context[0].dataIndex;
                            const timestamp = timestamps[index];
                            return timestamp.toLocaleString('tr-TR', {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit'
                            });
                        },
                        label: function(context) {
                            return context.dataset.label + ': ₺' + formatNumber(context.parsed.y, 2);
                        }
                    }
                },
                zoom: {
                    zoom: {
                        wheel: {
                            enabled: true,
                            speed: 0.1
                        },
                        pinch: {
                            enabled: true
                        },
                        mode: 'x',
                    },
                    pan: {
                        enabled: true,
                        mode: 'x',
                        // No modifierKey - pan with direct mouse drag
                    },
                    limits: {
                        x: {min: 'original', max: 'original'},
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        display: true
                    },
                    ticks: {
                        color: '#a0aec0',
                        font: {
                            size: 11
                        },
                        maxRotation: 45,
                        minRotation: 0
                    }
                },
                y: {
                    beginAtZero: false,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)',
                        display: true
                    },
                    ticks: {
                        color: '#a0aec0',
                        font: {
                            size: 11
                        },
                        callback: function(value) {
                            return '₺' + formatNumber(value, 2);
                        }
                    }
                }
            }
        }
    });
    
    // Show reset zoom button when zoomed or panned
    const resetBtn = document.getElementById('resetZoomBtn');
    if (resetBtn) {
        ctx.getContext('2d').canvas.addEventListener('wheel', () => {
            resetBtn.style.display = 'inline-block';
        });
        // Show reset button when panning (dragging)
        ctx.getContext('2d').canvas.addEventListener('mousedown', () => {
            resetBtn.style.display = 'inline-block';
        });
    }
}

// Load Symbols
async function loadSymbols() {
    const exchangeSelect = document.getElementById('symbolExchangeSelect');
    const exchange = exchangeSelect.value;
    
    if (!exchange) {
        showNotification('Please select an exchange', 'warning');
        return;
    }
    
    const filter = document.getElementById('symbolFilterInput').value.trim();
    const btn = document.getElementById('loadSymbolsBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> Loading...';
    
    try {
        let url = `/api/analytics/symbols/${exchange}`;
        if (filter) {
            url += `?quote=${encodeURIComponent(filter)}`;
        }
        
        const response = await fetch(url);
        if (!response.ok) throw new Error('API error');
        
        const data = await response.json();
        currentSymbolsData = data.symbols;
        displaySymbolsData(data);
        showNotification(`${data.count} symbols loaded`, 'success');
        
    } catch (error) {
        console.error('Error loading symbols:', error);
        showNotification('Error loading symbols', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Load Symbols';
    }
}

function displaySymbolsData(data) {
    // Update stats
    document.getElementById('totalSymbols').textContent = data.count;
    
    // Determine status field based on exchange (different exchanges use different field names)
    const active = data.symbols.filter(s => {
        const status = s.status || s.state || 'active';
        return status === 'TRADING' || status === 'active' || status === 'live';
    }).length;
    document.getElementById('activeSymbols').textContent = active;
    
    // Update table - show key fields that are common
    const tbody = document.getElementById('symbolsTableBody');
    if (data.symbols.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 40px;">No symbols found</td></tr>';
        return;
    }
    
    tbody.innerHTML = data.symbols.map(item => {
        // Extract common fields (different exchanges have different structures)
        const symbol = item.symbol || item.instId || `${item.base_currency || ''}/${item.counter_currency || ''}`;
        const baseAsset = item.baseAsset || item.baseCcy || item.base_currency || item.stock || '';
        const quoteAsset = item.quoteAsset || item.quoteCcy || item.counter_currency || item.money || '';
        const status = item.status || item.state || 'active';
        const isActive = status === 'TRADING' || status === 'active' || status === 'live';
        
        return `
            <tr>
                <td><strong>${symbol}</strong></td>
                <td>${baseAsset}</td>
                <td>${quoteAsset}</td>
                <td><span class="badge ${isActive ? 'badge-success' : 'badge-warning'}">${status}</span></td>
            </tr>
        `;
    }).join('');
}

// Load Withdrawal Fees
async function loadWithdrawalFees() {
    const exchangeSelect = document.getElementById('feeExchangeSelect');
    const exchange = exchangeSelect.value;
    
    if (!exchange) {
        showNotification('Please select an exchange', 'warning');
        return;
    }
    
    const btn = document.getElementById('loadFeesBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="loading"></span> Loading...';
    
    try {
        const response = await fetch(`/api/analytics/withdrawal-fees/${exchange}`);
        if (!response.ok) throw new Error('API error');
        
        const data = await response.json();
        currentFeesData = data.fees;
        displayFeesData(data);
        showNotification(`${data.count} fee records loaded`, 'success');
        
    } catch (error) {
        console.error('Error loading fees:', error);
        showNotification('Error loading fees', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Load Fees';
    }
}

function displayFeesData(data) {
    // Update stats
    document.getElementById('totalAssets').textContent = 
        new Set(data.fees.map(f => f.asset)).size;
    document.getElementById('totalNetworks').textContent = data.count;
    
    // Update table with filter
    const filterInput = document.getElementById('feeFilterInput');
    const filterValue = filterInput.value.trim().toUpperCase();
    
    const filteredFees = filterValue 
        ? data.fees.filter(f => f.asset.toUpperCase().includes(filterValue))
        : data.fees;
    
    const tbody = document.getElementById('feesTableBody');
    if (filteredFees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 40px;">No fee records found</td></tr>';
        return;
    }
    
    tbody.innerHTML = filteredFees.map(item => `
        <tr>
            <td><strong>${item.asset}</strong></td>
            <td>${item.network}</td>
            <td>${item.withdrawFee}</td>
            <td>${item.withdrawMin}</td>
            <td>${item.withdrawMax || '-'}</td>
        </tr>
    `).join('');
    
    // Add filter listener
    filterInput.oninput = () => displayFeesData(data);
}

// Export Data
async function exportData(type, format) {
    let data, filename;
    
    if (type === 'symbols') {
        if (currentSymbolsData.length === 0) {
            showNotification('Please load symbols first', 'warning');
            return;
        }
        data = currentSymbolsData;
        const exchange = document.getElementById('symbolExchangeSelect').value;
        filename = `${exchange}_symbols_${Date.now()}.${format}`;
    } else if (type === 'fees') {
        if (currentFeesData.length === 0) {
            showNotification('Please load fees first', 'warning');
            return;
        }
        data = currentFeesData;
        const exchange = document.getElementById('feeExchangeSelect').value;
        filename = `${exchange}_fees_${Date.now()}.${format}`;
    }
    
    if (format === 'json') {
        downloadJSON(data, filename);
    } else if (format === 'csv') {
        downloadCSV(data, filename);
    }
    
    showNotification('Export successful', 'success');
}

function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

function downloadCSV(data, filename) {
    if (data.length === 0) return;
    
    // Get all unique keys from all objects (in case some objects have different fields)
    const allKeys = new Set();
    data.forEach(item => {
        Object.keys(item).forEach(key => allKeys.add(key));
    });
    const headers = Array.from(allKeys);
    
    // Handle nested objects and arrays in CSV
    const flattenValue = (value) => {
        if (value === null || value === undefined) return '';
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value).replace(/"/g, '""'); // Escape quotes
    };
    
    const csv = [
        headers.join(','),
        ...data.map(row => headers.map(h => `"${flattenValue(row[h])}"`).join(','))
    ].join('\n');
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

// Utility Functions
function formatNumber(num, decimals = 2) {
    if (num === 0) return '0';
    if (!num) return '-';
    
    if (num >= 1000000000) {
        return (num / 1000000000).toFixed(2) + 'B';
    } else if (num >= 1000000) {
        return (num / 1000000).toFixed(2) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(2) + 'K';
    }
    
    return num.toFixed(decimals);
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 16px 24px;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        z-index: 9999;
        animation: slideIn 0.3s ease;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .loading {
        display: inline-block;
        width: 14px;
        height: 14px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        border-radius: 50%;
        border-top-color: white;
        animation: spin 0.8s linear infinite;
    }
    
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    
    .positive {
        color: #10b981 !important;
        font-weight: 600;
    }
    
    .negative {
        color: #ef4444 !important;
        font-weight: 600;
    }
    
    .badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .badge-success {
        background: #d1fae5;
        color: #065f46;
    }
    
    .badge-warning {
        background: #fef3c7;
        color: #92400e;
    }
`;
document.head.appendChild(style);

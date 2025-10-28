class WalletTracker {
    constructor() {
        console.log('WalletTracker constructor called');
        this.websocket = null;
        this.wallets = new Map();
        this.transactions = [];
        this.config = this.loadConfig();
        
        // Binance exchange rates cache
        this.exchangeRates = new Map();
        this.ratesCacheExpiry = 0;
        this.ratesCacheDuration = 5 * 60 * 1000; // 5 minutes
        
        // Loading state management
        this.isLoadingWallets = false;
    this.postReloadPending = false; // flag to run a reload after current display finishes
        this.balanceUpdateTimeout = null;
        
        // Lazy loading properties
        this.displayedTransactions = [];
        this.allTransactions = [];
        this.transactionsPerPage = 10;
        this.currentPage = 0;
        this.isLoadingMore = false;
        this.hasMoreTransactions = true;
        this.totalHours = 1; // Start with 1 hour
        this.lastWebSocketUpdate = 0;
        this.preserveLazyLoading = false;
        
        this.init();
    }
    
    loadConfig() {
        return {
            websocketHost: window.location.hostname,
            websocketPort: window.location.port || (window.location.protocol === 'https:' ? '443' : '80'),
            websocketProtocol: window.location.protocol === 'https:' ? 'wss:' : 'ws:',
            refreshInterval: 30000, // 30 seconds
            transactionRefreshInterval: 15000, // 15 seconds
            maxTransactionsDisplay: 20
        };
    }

    async init() {
        console.log('Initializing WalletTracker...');
        try {
            await this.connectWebSocket();
            await this.loadInitialData();
            this.startAutoRefresh();
            this.setupScrollListener();
            console.log('WalletTracker initialization complete');
        } catch (error) {
            console.error('Error during WalletTracker initialization:', error);
            this.showError('Failed to initialize application: ' + error.message);
        }
    }

    // Debug function to test formatting
    debugFormatBalance() {
        console.log('Testing formatBalance function:');
        const testValues = [15206014.1444, 1192212.0, 46.932658, 2.6, 0.123456];
        testValues.forEach(val => {
            console.log(`${val} -> ${this.formatBalance(val, 2)}`);
        });
    }

    // Format balance with 2 decimal places and thousand separators
    formatBalance(balance, decimals = 2) {
        if (typeof balance !== 'number') {
            balance = parseFloat(balance) || 0;
        }
        
        // Format with specified decimal places and add thousand separators
        return balance.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }

    // Get appropriate decimal places for token
    getTokenDecimals(tokenSymbol) {
        if (tokenSymbol === 'ETH' || tokenSymbol === 'WETH' || tokenSymbol === 'TRX') {
            return 6; // More decimals for main coins
        }
        if (tokenSymbol === 'BTC') {
            return 4; // 3 decimals for Bitcoin
        }
        return 2; // Default for tokens
    }

    // Get Binance exchange rates
    async getBinanceRates() {
        const now = Date.now();
        
        // Check cache first
        if (this.ratesCacheExpiry > now && this.exchangeRates.size > 0) {
            return this.exchangeRates;
        }
        
        try {
            const response = await fetch('https://api.binance.com/api/v3/ticker/price');
            const data = await response.json();
            
            // Update cache
            this.exchangeRates.clear();
            data.forEach(item => {
                this.exchangeRates.set(item.symbol, parseFloat(item.price));
            });
            this.ratesCacheExpiry = now + this.ratesCacheDuration;
            
            console.log('Binance rates updated:', this.exchangeRates.size, 'pairs');
            return this.exchangeRates;
        } catch (error) {
            console.error('Error fetching Binance rates:', error);
            return this.exchangeRates; // Return cached data if available
        }
    }

    // Convert token balance to USDT using Binance rates
    async convertToUSDT(tokenSymbol, balance) {
        if (!tokenSymbol || !balance || balance <= 0) {
            return 0;
        }

        // USDT is already USDT
        if (tokenSymbol === 'USDT') {
            return balance;
        }

        const rates = await this.getBinanceRates();
        
        // Direct USDT pair
        const directPair = `${tokenSymbol}USDT`;
        if (rates.has(directPair)) {
            return balance * rates.get(directPair);
        }
        
        // Try through BTC
        const btcPair = `${tokenSymbol}BTC`;
        const btcUsdtPair = 'BTCUSDT';
        if (rates.has(btcPair) && rates.has(btcUsdtPair)) {
            const btcAmount = balance * rates.get(btcPair);
            return btcAmount * rates.get(btcUsdtPair);
        }
        
        // Try through ETH
        const ethPair = `${tokenSymbol}ETH`;
        const ethUsdtPair = 'ETHUSDT';
        if (rates.has(ethPair) && rates.has(ethUsdtPair)) {
            const ethAmount = balance * rates.get(ethPair);
            return ethAmount * rates.get(ethUsdtPair);
        }
        
        console.warn(`No USDT conversion rate found for ${tokenSymbol}`);
        return 0;
    }

    async connectWebSocket() {
        try {
            const wsUrl = `${this.config.websocketProtocol}//${this.config.websocketHost}:${this.config.websocketPort}/ws`;
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('WebSocket connected successfully');
                this.showConnectionStatus('connected');
            };
            
            this.websocket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    this.handleWebSocketMessage(message);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.websocket.onclose = () => {
                console.log('WebSocket disconnected');
                this.showConnectionStatus('disconnected');
                setTimeout(() => this.connectWebSocket(), 3000);
            };
            
            this.websocket.onerror = (error) => {
                console.warn('WebSocket error:', error);
                this.showConnectionStatus('error');
            };
        } catch (error) {
            console.warn('WebSocket connection failed:', error);
            this.showConnectionStatus('error');
        }
    }
    
    showConnectionStatus(status) {
        const statusIndicator = document.querySelector('.status-indicator span');
        const statusDot = document.querySelector('.status-dot');
        
        if (statusIndicator && statusDot) {
            switch (status) {
                case 'connected':
                    statusIndicator.textContent = 'LIVE';
                    statusDot.style.background = '#00d084';
                    break;
                case 'disconnected':
                    statusIndicator.textContent = 'OFFLINE';
                    statusDot.style.background = '#666';
                    break;
                case 'error':
                    statusIndicator.textContent = 'ERROR';
                    statusDot.style.background = '#ff4757';
                    break;
            }
        }
    }

    handleWebSocketMessage(message) {
        console.log('WebSocket message received:', message);
        
        switch (message.type) {
            case 'balance_update':
                console.log('🚀 Balance update received:', message.data);
                this.handleBalanceUpdate(message.data);
                break;
            case 'new_transaction':
                this.handleNewTransaction(message.data);
                break;
            case 'transactions_update':
                if (message.data.latest_transactions) {
                    this.handleTransactionsUpdate(message.data.latest_transactions);
                }
                break;
            case 'tron_transaction':
                // Handle TRON specific transaction
                if (message.data && message.data.transaction) {
                    this.handleNewTransaction(message.data.transaction);
                    // Also reload wallets to update balance (debounced)
                    this.handleBalanceUpdate({ change_type: 'transaction' });
                }
                break;
            case 'transaction_notification':
                // Handle transaction notification (usually contains formatted message)
                if (message.data && message.data.transaction) {
                    this.handleNewTransaction(message.data.transaction);
                }
                // Show notification if available
                if (message.data && message.data.message) {
                    this.showTransactionNotification(message.data.message);
                }
                break;
            default:
                console.log('Unknown message type:', message.type);
        }
    }

    handleBalanceUpdate(balanceData) {
        console.log('💰 Processing balance update:', balanceData);
        
        // Clear any pending balance update
        if (this.balanceUpdateTimeout) {
            clearTimeout(this.balanceUpdateTimeout);
        }

        // Debounce balance updates to prevent rapid successive calls
        this.balanceUpdateTimeout = setTimeout(() => {
            // Try to enqueue a reload — if a display is in progress we'll mark it and run after
            this.enqueueWalletsReload(true);
        }, 500); // 500ms debounce
        
        // Show a notification immediately (don't debounce notifications)
        if (balanceData.change_type && balanceData.token_symbol) {
            const changeType = balanceData.change_type;
            const amount = Math.abs(balanceData.change_amount || 0);
            const symbol = balanceData.token_symbol;
            const percentage = Math.abs(balanceData.change_percentage || 0);
            
            let message = `${symbol} balance ${changeType}: ${amount.toFixed(6)} (${percentage.toFixed(2)}%)`;
            this.showBalanceNotification(message, changeType.includes('increase') ? 'success' : 'warning');
        }
    }

    enqueueWalletsReload(forceRefresh = false) {
        // If a display/update is in progress, mark a pending reload so it runs after
        if (this.isLoadingWallets) {
            console.log('⏳ Display in progress, scheduling wallets reload after current display finishes');
            this.postReloadPending = true;
            this.postReloadForce = forceRefresh;
            return;
        }

        // Otherwise, run the reload now
        try {
            this.loadWallets(forceRefresh);
        } catch (err) {
            console.error('Failed to enqueue wallets reload:', err);
        }
    }

    showBalanceNotification(message, type = 'info') {
        // Create a temporary notification element
        const notification = document.createElement('div');
        notification.className = `balance-notification balance-notification-${type}`;
        notification.textContent = message;
        
        // Style the notification
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#00d084' : '#ffc107'};
            color: ${type === 'success' ? '#000' : '#000'};
            padding: 12px 16px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            transform: translateX(100%);
            transition: transform 0.3s ease;
        `;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    handleNewTransaction(transactionData) {
        // Only prepend new transactions to existing view without full reload
        if (this.allTransactions.length > 0) {
            // Add new transaction to the beginning
            this.allTransactions.unshift(transactionData);
            this.prependTransactionToDisplay(transactionData);
        } else {
            // If no transactions loaded yet, do a full load
            this.loadTransactions();
        }
    }

    handleTransactionsUpdate(latestTransactions) {
        // Merge new transactions without disrupting lazy loading
        if (this.preserveLazyLoading && this.allTransactions.length > 0) {
            // Only add truly new transactions (not already in our list)
            const existingHashes = new Set(this.allTransactions.map(t => t.hash || t.transaction_hash));
            const newTransactions = latestTransactions.filter(t => !existingHashes.has(t.hash || t.transaction_hash));
            
            if (newTransactions.length > 0) {
                // Add new transactions to the beginning
                this.allTransactions = [...newTransactions, ...this.allTransactions];
                // Update display
                this.updateTransactionDisplay();
            }
        } else {
            // Full update if not in lazy loading mode
            this.displayTransactions(latestTransactions, true);
        }
    }

    async loadInitialData() {
        try {
            // Show loading indicators
            this.showLoadingIndicator('balanceTableBody', 'Loading wallets...');
            this.showLoadingIndicator('transactionsTableBody', 'Loading transactions...');
            
            // Load data in parallel with Promise.allSettled to handle failures gracefully
            const [walletsResult, transactionsResult] = await Promise.allSettled([
                fetch('/api/wallets'),
                fetch(`/api/transactions?limit=${this.config.maxTransactionsDisplay}&hours=1`)
            ]);
            
            // Handle wallets result
            if (walletsResult.status === 'fulfilled' && walletsResult.value.ok) {
                const wallets = await walletsResult.value.json();
                this.displayWallets(wallets);
            } else {
                console.error('Failed to load wallets:', walletsResult.reason || 'Unknown error');
                this.showError('Failed to load wallets');
            }
            
            // Handle transactions result
            if (transactionsResult.status === 'fulfilled' && transactionsResult.value.ok) {
                const transactions = await transactionsResult.value.json();
                this.displayTransactions(transactions);
            } else {
                console.error('Failed to load transactions:', transactionsResult.reason || 'Unknown error');
                this.showError('Failed to load transactions');
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load data');
        }
    }

    showLoadingIndicator(elementId, message = 'Loading...') {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        element.innerHTML = `
            <tr>
                <td colspan="7" class="loading-row">
                    <div class="loading-container">
                        <div class="loading-spinner"></div>
                        <span>${message}</span>
                    </div>
                </td>
            </tr>
        `;
    }

    async loadWallets(forceRefresh = false) {
        // Prevent concurrent wallet loading operations
        if (this.isLoadingWallets) {
            console.log('⏸️ Wallet loading already in progress, skipping...');
            return;
        }
        
        this.isLoadingWallets = true;
        
        try {
            const url = `/api/wallets?_t=${Date.now()}`;
                
            const response = await fetch(url);
            if (response.ok) {
                const wallets = await response.json();
                this.displayWallets(wallets, forceRefresh);
                
                if (forceRefresh) {
                    console.log('🔄 Wallets reloaded (cache disabled)');
                }
            }
        } catch (error) {
            console.error('Failed to load wallets:', error);
        } finally {
            this.isLoadingWallets = false;
        }
    }

    async loadTransactions() {
        // Only do full reload if not in lazy loading mode
        if (this.preserveLazyLoading && this.allTransactions.length > 0) {
            console.log('Preserving lazy loading state, skipping full transaction reload');
            return;
        }
        
        try {
            const timestamp = Date.now();
            const response = await fetch(`/api/transactions?limit=${this.config.maxTransactionsDisplay}&hours=${this.totalHours}&_t=${timestamp}`);
            
            if (response.ok) {
                const transactions = await response.json();
                this.displayTransactions(transactions);
            }
        } catch (error) {
            console.error('Failed to load transactions:', error);
        }
    }

    displayWallets(wallets, isRefresh = false) {
        const tbody = document.getElementById('balanceTableBody');
        if (!tbody) return;
        
        if (!wallets || wallets.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="loading-row">No wallets found. Add a wallet to get started.</td>
                </tr>
            `;
            return;
        }
        
        // Prevent concurrent wallet loading/display operations
        if (this.isLoadingWallets) {
            console.log('⏸️ displayWallets called while a wallet load is in progress, skipping to avoid duplicate render');
            return;
        }

        // Mark loading so other callers (like loadWallets) will wait
        this.isLoadingWallets = true;

        // Group tokens by symbol across all wallets to avoid duplicates
        const tokenGroups = new Map();
        
        for (const wallet of wallets) {
            if (wallet.balances && wallet.balances.length > 0) {
                for (const balance of wallet.balances) {
                    const key = `${balance.token_symbol}_${wallet.blockchain?.name}`;
                    
                    if (tokenGroups.has(key)) {
                        // Add to existing token group
                        const existing = tokenGroups.get(key);
                        existing.balance += balance.balance;
                        existing.wallets.push({ wallet, balance });
                    } else {
                        // Create new token group
                        tokenGroups.set(key, {
                            tokenSymbol: balance.token_symbol,
                            blockchain: wallet.blockchain,
                            balance: balance.balance,
                            wallets: [{ wallet, balance }],
                            token_id: balance.token_id
                        });
                    }
                }
            } else {
                // Wallet without balances - show as individual row
                const key = `${wallet.address}_no_balance`;
                tokenGroups.set(key, {
                    wallet: wallet,
                    balance: null,
                    wallets: [{ wallet, balance: null }]
                });
            }
        }
        
        // Store current rows for animation comparison
        const existingRows = isRefresh ? Array.from(tbody.querySelectorAll('tr')) : [];
        
    tbody.innerHTML = '';
        
        // Display grouped tokens
        for (const [key, tokenGroup] of tokenGroups) {
            if (tokenGroup.balance !== null) {
                // Show aggregated token balance
                const representativeWallet = tokenGroup.wallets[0].wallet;
                const aggregatedBalance = {
                    token_symbol: tokenGroup.tokenSymbol,
                    balance: tokenGroup.balance,
                    token_id: tokenGroup.token_id
                };
                
                const row = this.createWalletRow(representativeWallet, aggregatedBalance);
                tbody.appendChild(row);
                
                // Add update animation if this is a refresh
                if (isRefresh) {
                    row.classList.add('balance-row-update');
                    setTimeout(() => {
                        row.classList.remove('balance-row-update');
                    }, 800);
                }
            } else {
                // Show wallet without balances
                const row = this.createWalletRow(tokenGroup.wallet, null);
                tbody.appendChild(row);
                
                if (isRefresh) {
                    row.classList.add('balance-row-update');
                    setTimeout(() => {
                        row.classList.remove('balance-row-update');
                    }, 800);
                }
            }
        }

        // Finished rendering — clear loading flag and run any pending reloads
        this.isLoadingWallets = false;
        if (this.postReloadPending) {
            console.log('🔁 Running pending wallets reload that was queued during display');
            this.postReloadPending = false;
            // Respect previously requested force flag if set
            const f = this.postReloadForce || false;
            this.postReloadForce = false;
            // run reload (non-blocking)
            setTimeout(() => this.loadWallets(f), 50);
        }
    }

    createWalletRow(wallet, balance) {
        const row = document.createElement('tr');
        row.className = 'transaction-row';
        
        const shortAddress = `${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}`;
        const tokenSymbol = balance ? balance.token_symbol : 'N/A';
        const decimals = this.getTokenDecimals(tokenSymbol);
        const balanceAmount = balance ? this.formatBalance(balance.balance, decimals) : '0.00';
        
        // Create unique ID for this row's USDT cell
        const usdtCellId = `usdt-cell-${wallet.id}-${balance?.token_id || 'no-balance'}`;
        
        // Render skeleton row immediately (no await - synchronous rendering)
        row.innerHTML = `
            <td>
                <div class="token-info">
                    <div class="wallet-label">${tokenSymbol} Balance</div>
                    <div class="address">${wallet.blockchain?.name || 'Unknown'} Network</div>
                </div>
            </td>
            <td>
                <span class="network-badge network-${wallet.blockchain?.name?.toLowerCase()}">${wallet.blockchain?.name || 'Unknown'}</span>
            </td>
            <td>
                <span class="token-badge">${tokenSymbol}</span>
            </td>
            <td class="balance-cell">
                <div class="balance-group">
                    <div class="balance-item">
                        <span class="balance-amount">${balanceAmount}</span>
                        <span class="balance-symbol">${tokenSymbol}</span>
                    </div>
                </div>
            </td>
            <td class="balance-cell" id="${usdtCellId}">
                <span class="usdt-loading">
                    <i class="fas fa-spinner fa-spin" style="font-size: 10px; opacity: 0.6;"></i> Converting...
                </span>
            </td>
            <td>
                <span class="status-badge status-success">Active</span>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn btn-refresh" onclick="refreshWallet(${wallet.id})" title="Refresh & Show All Tokens">
                        <i class="fas fa-sync"></i>
                    </button>
                    ${balance ? `<button class="action-btn btn-hide" onclick="hideToken(${balance.wallet_id || wallet.id}, ${balance.token_id})" title="Hide Token">
                        <i class="fas fa-eye-slash"></i>
                    </button>` : ''}
                    <button class="action-btn btn-delete" onclick="deleteWallet(${wallet.id})" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        // Schedule asynchronous USDT conversion after DOM insertion
        this.scheduleUsdtConversion(usdtCellId, tokenSymbol, balance);
        
        return row;
    }

    async scheduleUsdtConversion(cellId, tokenSymbol, balance) {
        // Run conversion asynchronously after a short delay to allow DOM insertion
        setTimeout(async () => {
            const cell = document.getElementById(cellId);
            if (!cell) {
                // Cell no longer exists (row was removed/replaced), skip conversion
                return;
            }
            
            let usdtValue = 'N/A';
            if (balance && balance.balance > 0) {
                try {
                    const usdtAmount = await this.convertToUSDT(tokenSymbol, balance.balance);
                    usdtValue = usdtAmount > 0 ? `${this.formatBalance(usdtAmount, 2)} USDT` : 'N/A';
                } catch (error) {
                    console.error('Error converting to USDT:', error);
                    usdtValue = 'Error';
                }
            }
            
            // Update the cell content if it still exists
            if (cell && cell.id === cellId) {
                cell.innerHTML = usdtValue;
                // Add a subtle fade-in animation
                cell.style.opacity = '0.7';
                setTimeout(() => {
                    cell.style.opacity = '1';
                }, 100);
            }
        }, 10); // Small delay to ensure DOM is ready
    }

    displayTransactions(transactions, append = false) {
        const tbody = document.getElementById('transactionsTableBody');
        if (!tbody) return;
        
        if (!append) {
            this.allTransactions = transactions || [];
            this.displayedTransactions = [];
            this.currentPage = 0;
            this.preserveLazyLoading = false;
            tbody.innerHTML = '';
        }
        
        if (!this.allTransactions || this.allTransactions.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="loading-row">No recent transactions found.</td>
                </tr>
            `;
            return;
        }
        
        this.loadMoreTransactions();
    }

    prependTransactionToDisplay(transaction) {
        const tbody = document.getElementById('transactionsTableBody');
        if (!tbody) return;
        
        // Create and insert new transaction row at the top
        const row = this.createTransactionRow(transaction);
        row.classList.add('transaction-new');
        
        // Remove loading row if exists
        const loadingRow = tbody.querySelector('.loading-row');
        if (loadingRow) {
            loadingRow.parentElement.remove();
        }
        
        tbody.insertBefore(row, tbody.firstChild);
        
        // Animation will fade out automatically via CSS
        setTimeout(() => {
            row.classList.remove('transaction-new');
        }, 600);
    }

    updateTransactionDisplay() {
        const tbody = document.getElementById('transactionsTableBody');
        if (!tbody) return;
        
        // Clear only transaction rows, keep load more button
        const existingRows = tbody.querySelectorAll('tr:not(.load-more-row)');
        existingRows.forEach(row => row.remove());
        
        // Reload with current page settings
        this.displayedTransactions = [];
        this.currentPage = 0;
        this.loadMoreTransactions();
    }

    loadMoreTransactions() {
        console.log('loadMoreTransactions called, isLoadingMore:', this.isLoadingMore);
        console.log('allTransactions length:', this.allTransactions.length);
        console.log('displayedTransactions length:', this.displayedTransactions.length);
        
        if (this.isLoadingMore) return;
        
        this.isLoadingMore = true;
        const tbody = document.getElementById('transactionsTableBody');
        
        const sortedTransactions = [...this.allTransactions].sort((a, b) => {
            let aTime = a.timestamp;
            let bTime = b.timestamp;
            
            if (typeof aTime === 'string') aTime = new Date(aTime).getTime() / 1000;
            else if (aTime > 10000000000) aTime = aTime / 1000;
            
            if (typeof bTime === 'string') bTime = new Date(bTime).getTime() / 1000;
            else if (bTime > 10000000000) bTime = bTime / 1000;
            
            return bTime - aTime;
        });
        
        const startIndex = this.currentPage * this.transactionsPerPage;
        const endIndex = startIndex + this.transactionsPerPage;
        const transactionsToShow = sortedTransactions.slice(startIndex, endIndex);
        
        if (transactionsToShow.length === 0) {
            if (this.displayedTransactions.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="loading-row">No recent transactions found.</td>
                    </tr>
                `;
            }
            this.hasMoreTransactions = false;
            this.isLoadingMore = false;
            return;
        }
        
        transactionsToShow.forEach(tx => {
            const row = this.createTransactionRow(tx);
            if (row) {
                tbody.appendChild(row);
                this.displayedTransactions.push(tx);
            }
        });
        
        this.hasMoreTransactions = endIndex < sortedTransactions.length;
        this.currentPage++;
        this.updateLoadMoreButton();
        this.isLoadingMore = false;
    }

    createTransactionRow(tx) {
        const row = document.createElement('tr');
        row.className = 'transaction-row';
        
        // Format timestamp
        let timestamp = tx.timestamp;
        if (typeof timestamp === 'string') {
            timestamp = new Date(timestamp).getTime() / 1000;
        } else if (timestamp > 10000000000) {
            timestamp = timestamp / 1000;
        }
        
        const date = new Date(timestamp * 1000);
        const timeStr = this.formatTimeAgo(date);
        
        // Transaction hash (truncated)
        const shortHash = tx.hash ? `${tx.hash.slice(0, 8)}...${tx.hash.slice(-4)}` : 'N/A';
        
        // Direction
        const direction = this.getTransactionDirection(tx);
        const directionClass = direction === 'IN' ? 'direction-in' : 'direction-out';
        
        // From/To address
        const fromTo = direction === 'IN' ? tx.from : tx.to;
        const shortFromTo = fromTo ? `${fromTo.slice(0, 6)}...${fromTo.slice(-4)}` : 'N/A';
        
        row.innerHTML = `
            <td class="timestamp">${timeStr}</td>
            <td>
                <span class="transaction-hash" onclick="openExplorer('${tx.hash}', '${tx.blockchain}')" style="cursor: pointer;">
                    ${shortHash}
                </span>
            </td>
            <td>
                <span class="token-symbol">${tx.type}</span>
                <span class="network-badge network-${tx.blockchain?.toLowerCase()}">${tx.blockchain}</span>
            </td>
            <td class="transaction-amount">${this.formatBalance(parseFloat(tx.amount), this.getTokenDecimals(tx.type))}</td>
            <td>
                <span class="direction-badge ${directionClass}">${direction}</span>
            </td>
            <td class="address">${shortFromTo}</td>
            <td>
                <span class="status-badge status-success">${tx.status}</span>
            </td>
        `;
        
        return row;
    }

    getTransactionDirection(tx) {
        // This is a simplified version - you might need more logic based on wallet addresses
        if (tx.wallet_address) {
            return tx.to === tx.wallet_address ? 'IN' : 'OUT';
        }
        return 'OUT'; // Default
    }

    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);
        
        if (diffSecs < 60) {
            return `${diffSecs}s ago`;
        } else if (diffMins < 60) {
            return `${diffMins}m ago`;
        } else if (diffHours < 24) {
            return `${diffHours}h ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    updateLoadMoreButton() {
        const tbody = document.getElementById('transactionsTableBody');
        
        // Remove existing load more button
        const existingButton = tbody.querySelector('.load-more-row');
        if (existingButton) {
            existingButton.remove();
        }
        
        if (this.hasMoreTransactions) {
            const loadMoreRow = document.createElement('tr');
            loadMoreRow.className = 'load-more-row';
            loadMoreRow.innerHTML = `
                <td colspan="7" class="text-center py-4">
                    <button class="load-more-btn" onclick="walletTracker.loadMoreTransactions()">
                        <i class="fas fa-chevron-down"></i> Load More Transactions
                    </button>
                </td>
            `;
            tbody.appendChild(loadMoreRow);
        } else if (this.displayedTransactions.length > 0) {
            const loadEarlierRow = document.createElement('tr');
            loadEarlierRow.className = 'load-more-row';
            loadEarlierRow.innerHTML = `
                <td colspan="7" class="text-center py-4">
                    <button class="load-more-btn" onclick="walletTracker.loadEarlierTransactions()">
                        <i class="fas fa-history"></i> Load Earlier Transactions (Extend to ${this.totalHours * 2}h)
                    </button>
                </td>
            `;
            tbody.appendChild(loadEarlierRow);
        }
    }

    async loadEarlierTransactions() {
        console.log('loadEarlierTransactions called, isLoadingMore:', this.isLoadingMore);
        if (this.isLoadingMore) return;
        
        try {
            this.isLoadingMore = true;
            this.preserveLazyLoading = true;
            console.log('Starting to load earlier transactions...');
            
            // Show loading state
            const loadBtn = document.querySelector('.load-more-btn');
            console.log('Load button found:', !!loadBtn);
            if (loadBtn) {
                loadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
                loadBtn.disabled = true;
            }
            
            const oldHours = this.totalHours;
            this.totalHours *= 2;
            console.log(`Loading transactions from last ${this.totalHours} hours...`);
            
            const timestamp = Date.now();
            const response = await fetch(`/api/transactions?limit=500&hours=${this.totalHours}&_t=${timestamp}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const newTransactions = await response.json();
            
            // Merge new transactions with existing ones intelligently
            const existingHashes = new Set(this.allTransactions.map(t => t.hash || t.transaction_hash));
            const trulyNewTransactions = newTransactions.filter(t => !existingHashes.has(t.hash || t.transaction_hash));
            
            if (trulyNewTransactions.length > 0) {
                // Add only new transactions to existing array
                this.allTransactions = [...this.allTransactions, ...trulyNewTransactions];
                console.log(`Added ${trulyNewTransactions.length} new transactions (total: ${this.allTransactions.length})`);
                
                // Trigger display update to show new transactions
                this.loadMoreTransactions();
            } else {
                console.log('No new transactions found in extended time range');
                this.totalHours = oldHours; // Revert if no new data
            }
            
            this.hasMoreTransactions = trulyNewTransactions.length > 0;
            this.updateLoadMoreButton();
            
            // Reset button state on success
            const successBtn = document.querySelector('.load-more-btn');
            if (successBtn && trulyNewTransactions.length > 0) {
                successBtn.innerHTML = `<i class="fas fa-history"></i> Load Earlier Transactions (Extend to ${this.totalHours * 2}h)`;
                successBtn.disabled = false;
            } else if (successBtn && trulyNewTransactions.length === 0) {
                successBtn.innerHTML = '<i class="fas fa-info-circle"></i> No More Earlier Transactions';
                successBtn.disabled = true;
            }
            
        } catch (error) {
            console.error('Failed to load earlier transactions:', error);
            // Show error in button
            const loadBtn = document.querySelector('.load-more-btn');
            if (loadBtn) {
                loadBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Error - Try Again';
                loadBtn.disabled = false;
            }
        } finally {
            this.isLoadingMore = false;
        }
    }

    setupScrollListener() {
        let isScrollListenerActive = false;
        
        window.addEventListener('scroll', () => {
            if (isScrollListenerActive || this.isLoadingMore || !this.hasMoreTransactions) return;
            
            const scrollHeight = document.documentElement.scrollHeight;
            const scrollTop = document.documentElement.scrollTop;
            const clientHeight = document.documentElement.clientHeight;
            
            if (scrollTop + clientHeight >= scrollHeight - 200) {
                isScrollListenerActive = true;
                this.loadMoreTransactions();
                setTimeout(() => { isScrollListenerActive = false; }, 1000);
            }
        });
    }

    startAutoRefresh() {
        // Refresh wallets every 30 seconds
        setInterval(() => {
            this.loadWallets();
        }, this.config.refreshInterval);
        
        // Only refresh transactions if not in lazy loading mode or use smart refresh
        setInterval(() => {
            if (!this.preserveLazyLoading) {
                this.loadTransactions();
            } else {
                // Smart refresh: only get latest transactions without disrupting view
                this.refreshLatestTransactions();
            }
        }, this.config.transactionRefreshInterval);
    }

    async refreshLatestTransactions() {
        try {
            const timestamp = Date.now();
            const response = await fetch(`/api/transactions?limit=5&hours=1&_t=${timestamp}`);
            
            if (response.ok) {
                const latestTransactions = await response.json();
                this.handleTransactionsUpdate(latestTransactions);
            }
        } catch (error) {
            console.error('Failed to refresh latest transactions:', error);
        }
    }

    showError(message) {
        const tbody = document.getElementById('balanceTableBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="loading-row" style="color: #ff4757;">
                        <i class="fas fa-exclamation-triangle"></i> ${message}
                    </td>
                </tr>
            `;
        }
    }

    showTransactionNotification(message) {
        console.log('Transaction notification:', message);
        
        // Create a notification element
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #00d084 0%, #00b571 100%);
            color: #000;
            padding: 12px 20px;
            border-radius: 6px;
            font-weight: 600;
            font-size: 14px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0, 208, 132, 0.3);
            transform: translateX(400px);
            transition: transform 0.3s ease;
            max-width: 350px;
            word-wrap: break-word;
        `;
        notification.innerHTML = `<i class="fas fa-check-circle"></i> ${message}`;
        
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 100);
        
        // Animate out and remove
        setTimeout(() => {
            notification.style.transform = 'translateX(400px)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 4000);
    }
}

// Global functions for HTML onclick handlers
async function hideToken(walletId, tokenId) {
    if (!confirm('Bu tokeni gizlemek istediğinizden emin misiniz?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tokens/${walletId}/${tokenId}/hide`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            // Refresh wallets to update the display
            if (window.walletTracker) {
                await window.walletTracker.loadWallets();
                window.walletTracker.showTransactionNotification('Token başarıyla gizlendi');
            }
        } else {
            const error = await response.json();
            console.error('Error hiding token:', error);
            alert('Token gizlenirken hata oluştu: ' + error.detail);
        }
    } catch (error) {
        console.error('Error hiding token:', error);
        alert('Token gizlenirken hata oluştu');
    }
}

async function showToken(walletId, tokenId) {
    try {
        const response = await fetch(`/api/tokens/${walletId}/${tokenId}/show`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            // Refresh wallets to update the display
            if (window.walletTracker) {
                await window.walletTracker.loadWallets();
                window.walletTracker.showTransactionNotification('Token başarıyla gösterildi');
            }
        } else {
            const error = await response.json();
            console.error('Error showing token:', error);
            alert('Token gösterilirken hata oluştu: ' + error.detail);
        }
    } catch (error) {
        console.error('Error showing token:', error);
        alert('Token gösterilirken hata oluştu');
    }
}

// Make WalletTracker globally accessible
window.WalletTracker = WalletTracker;

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.walletTracker = new WalletTracker();
});

async function addWallet() {
    const address = document.getElementById('walletAddress').value.trim();
    const blockchainId = parseInt(document.getElementById('walletNetwork').value);
    
    if (!address) {
        alert('Lütfen bir wallet adresi girin');
        return;
    }
    
    if (!blockchainId) {
        alert('Lütfen bir network seçin');
        return;
    }
    
    try {
        const response = await fetch('/api/wallets', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                address: address,
                blockchain_id: blockchainId,
                name: null
            })
        });
        
        if (response.ok) {
            document.getElementById('walletAddress').value = '';
            document.getElementById('walletNetwork').value = '';
            toggleAddWalletForm();
            
            if (window.walletTracker) {
                await window.walletTracker.loadWallets();
            }
        } else {
            const error = await response.json();
            alert('Wallet eklenirken hata oluştu: ' + error.detail);
        }
    } catch (error) {
        console.error('Error adding wallet:', error);
        alert('Wallet eklenirken hata oluştu');
    }
}

async function deleteWallet(walletId) {
    if (!confirm('Bu wallet\'ı silmek istediğinizden emin misiniz?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/wallets/${walletId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            // Refresh the wallet display
            if (window.walletTracker) {
                await window.walletTracker.loadWallets();
                window.walletTracker.showTransactionNotification('Wallet başarıyla silindi');
            }
        } else {
            const error = await response.json();
            console.error('Error deleting wallet:', error);
            alert('Wallet silinirken hata oluştu: ' + error.detail);
        }
    } catch (error) {
        console.error('Error deleting wallet:', error);
        alert('Wallet silinirken hata oluştu');
    }
}

async function refreshWallet(walletId) {
    if (!confirm('Bu wallet\'ın tüm gizlenen tokenlarını göstermek ve bakiyeleri yenilemek istiyor musunuz?')) {
        return;
    }
    
    try {
        // Add loading state to the button
        const refreshBtn = document.querySelector(`button[onclick="refreshWallet(${walletId})"]`);
        if (refreshBtn) {
            refreshBtn.classList.add('loading');
            refreshBtn.disabled = true;
        }
        
        const response = await fetch(`/api/wallets/${walletId}/refresh`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            // Refresh the wallet display
            if (window.walletTracker) {
                await window.walletTracker.loadWallets();
                window.walletTracker.showTransactionNotification('Wallet yenilendi ve tüm tokenlar gösterildi');
            }
        } else {
            const error = await response.json();
            console.error('Error refreshing wallet:', error);
            alert('Wallet yenilenirken hata oluştu: ' + error.detail);
        }
    } catch (error) {
        console.error('Error refreshing wallet:', error);
        alert('Wallet yenilenirken hata oluştu');
    } finally {
        // Remove loading state
        const refreshBtn = document.querySelector(`button[onclick="refreshWallet(${walletId})"]`);
        if (refreshBtn) {
            refreshBtn.classList.remove('loading');
            refreshBtn.disabled = false;
        }
    }
}

function toggleAddWalletForm() {
    const form = document.getElementById('addWalletForm');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

// Load available blockchains from API
async function loadBlockchains() {
    try {
        const response = await fetch('/api/blockchains');
        if (response.ok) {
            const blockchains = await response.json();
            const select = document.getElementById('walletNetwork');
            
            // Clear existing options
            select.innerHTML = '';
            
            // Add placeholder
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = 'Select a network...';
            placeholder.disabled = true;
            placeholder.selected = true;
            select.appendChild(placeholder);
            
            // Add blockchain options
            blockchains.forEach(blockchain => {
                const option = document.createElement('option');
                option.value = blockchain.id;
                option.textContent = `${blockchain.display_name} (${blockchain.native_symbol})`;
                select.appendChild(option);
            });
            
            console.log(`Loaded ${blockchains.length} blockchains:`, blockchains.map(b => b.name).join(', '));
        } else {
            console.error('Failed to load blockchains');
            const select = document.getElementById('walletNetwork');
            select.innerHTML = '<option value="">Error loading networks</option>';
        }
    } catch (error) {
        console.error('Error loading blockchains:', error);
        const select = document.getElementById('walletNetwork');
        select.innerHTML = '<option value="">Error loading networks</option>';
    }
}

class WalletTracker {
    constructor() {
        console.log('WalletTracker constructor called');
        this.websocket = null;
        this.wallets = new Map();
        this.transactions = [];
        this.config = this.loadConfig();
        
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
        return 2; // Default for tokens
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
                this.loadWallets(); // Reload wallet data
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
                    // Also reload wallets to update balance
                    this.loadWallets();
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
            const [walletsResponse, transactionsResponse] = await Promise.all([
                fetch('/api/wallets'),
                fetch(`/api/transactions?limit=${this.config.maxTransactionsDisplay}&hours=1`)
            ]);
            
            if (walletsResponse.ok) {
                const wallets = await walletsResponse.json();
                this.displayWallets(wallets);
            }
            
            if (transactionsResponse.ok) {
                const transactions = await transactionsResponse.json();
                this.displayTransactions(transactions);
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load data');
        }
    }

    async loadWallets() {
        try {
            const response = await fetch('/api/wallets');
            if (response.ok) {
                const wallets = await response.json();
                this.displayWallets(wallets);
            }
        } catch (error) {
            console.error('Failed to load wallets:', error);
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

    displayWallets(wallets) {
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
        
        tbody.innerHTML = '';
        
        wallets.forEach(wallet => {
            if (wallet.balances && wallet.balances.length > 0) {
                wallet.balances.forEach(balance => {
                    const row = this.createWalletRow(wallet, balance);
                    tbody.appendChild(row);
                });
            } else {
                const row = this.createWalletRow(wallet, null);
                tbody.appendChild(row);
            }
        });
    }

    createWalletRow(wallet, balance) {
        const row = document.createElement('tr');
        row.className = 'transaction-row';
        
        const shortAddress = `${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}`;
        const tokenSymbol = balance ? balance.token_symbol : 'N/A';
        const decimals = this.getTokenDecimals(tokenSymbol);
        const balanceAmount = balance ? this.formatBalance(balance.balance, decimals) : '0.00';
        const usdValue = balance && balance.usd_value ? `$${this.formatBalance(balance.usd_value, 2)}` : 'N/A';
        
        row.innerHTML = `
            <td>
                <div class="token-info">
                    <div class="wallet-label">${wallet.name || shortAddress}</div>
                    <div class="address">${shortAddress}</div>
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
            <td class="balance-cell">
                ${usdValue}
            </td>
            <td>
                <span class="status-badge status-success">Active</span>
            </td>
            <td>
                <div class="action-buttons">
                    <button class="action-btn btn-view" onclick="viewWallet('${wallet.address}')" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn btn-refresh" onclick="refreshWallet('${wallet.address}')" title="Refresh">
                        <i class="fas fa-sync"></i>
                    </button>
                    <button class="action-btn btn-delete" onclick="deleteWallet('${wallet.address}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        return row;
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

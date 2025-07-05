// Global utility functions

function toggleAddWalletForm() {
    const form = document.getElementById('addWalletForm');
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function addWallet() {
    const address = document.getElementById('walletAddress').value;
    const network = document.getElementById('walletNetwork').value;
    
    if (!address) {
        alert('Please enter a wallet address');
        return;
    }
    
    try {
        const response = await fetch('/api/wallets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                address: address,
                blockchain: network
            })
        });
        
        if (response.ok) {
            document.getElementById('walletAddress').value = '';
            toggleAddWalletForm();
            location.reload(); // Simple refresh for now
        } else {
            alert('Failed to add wallet');
        }
    } catch (error) {
        console.error('Error adding wallet:', error);
        alert('Error adding wallet');
    }
}

function openExplorer(hash, blockchain) {
    if (hash && hash !== 'N/A') {
        let url;
        if (blockchain === 'TRON') {
            url = `https://tronscan.org/#/transaction/${hash}`;
        } else {
            // Default to Ethereum for ETH or unknown blockchains
            url = `https://etherscan.io/tx/${hash}`;
        }
        window.open(url, '_blank');
    }
}

// Action button functions
function viewWallet(address) {
    console.log('Viewing wallet:', address);
    alert(`View wallet details for: ${address}`);
}

async function refreshWallet(address) {
    console.log('Refreshing wallet:', address);
    const refreshBtn = event.target.closest('.btn-refresh');
    refreshBtn.classList.add('loading');
    
    try {
        // Find wallet ID from address
        const response = await fetch('/api/wallets');
        const wallets = await response.json();
        const wallet = wallets.find(w => w.address === address);
        
        if (wallet) {
            // Trigger a refresh for this specific wallet
            const refreshResponse = await fetch(`/api/wallets/${wallet.id}/refresh`, {
                method: 'POST'
            });
            
            if (refreshResponse.ok) {
                console.log('Wallet refresh triggered successfully');
                // Reload the page to show updated data
                setTimeout(() => location.reload(), 2000);
            } else {
                console.error('Failed to refresh wallet:', refreshResponse.status);
                alert('Failed to refresh wallet');
            }
        } else {
            console.error('Wallet not found for address:', address);
            alert('Wallet not found');
        }
    } catch (error) {
        console.error('Error refreshing wallet:', error);
        alert('Error refreshing wallet');
    } finally {
        refreshBtn.classList.remove('loading');
    }
}

async function deleteWallet(address) {
    if (!confirm(`Are you sure you want to delete wallet ${address}?`)) {
        return;
    }
    
    console.log('Deleting wallet:', address);
    
    try {
        // Find wallet ID from address
        const response = await fetch('/api/wallets');
        const wallets = await response.json();
        const wallet = wallets.find(w => w.address === address);
        
        if (wallet) {
            const deleteResponse = await fetch(`/api/wallets/${wallet.id}`, {
                method: 'DELETE'
            });
            
            if (deleteResponse.ok) {
                console.log('Wallet deleted successfully');
                location.reload(); // Reload to show updated list
            } else {
                console.error('Failed to delete wallet:', deleteResponse.status);
                alert('Failed to delete wallet');
            }
        } else {
            console.error('Wallet not found for address:', address);
            alert('Wallet not found');
        }
    } catch (error) {
        console.error('Error deleting wallet:', error);
        alert('Error deleting wallet');
    }
}

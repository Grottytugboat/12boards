// Mini Cart JavaScript - Modern Shopify Implementation

class MiniCart {
  constructor() {
    this.overlay = document.getElementById('mini-cart-overlay');
    this.drawer = document.getElementById('mini-cart-drawer');
    this.isUpdating = false;
    
    // Bind events
    this.bindEvents();
    
    // Initialize cart data
    this.updateCartDisplay();
  }
  
  bindEvents() {
    // Close on overlay click
    if (this.overlay) {
      this.overlay.addEventListener('click', (e) => {
        if (e.target === this.overlay) {
          this.close();
        }
      });
    }
    
    // Close on escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.overlay.classList.contains('active')) {
        this.close();
      }
    });
    
    // Cart trigger buttons (add these classes to your cart icons)
    document.addEventListener('click', (e) => {
      if (e.target.closest('.cart-trigger')) {
        e.preventDefault();
        this.open();
      }
    });
  }
  
  open() {
    document.body.style.overflow = 'hidden';
    this.overlay.classList.add('active');
    this.updateCartDisplay();
  }
  
  close() {
    document.body.style.overflow = '';
    this.overlay.classList.remove('active');
  }
  
  async updateQuantity(key, quantity) {
    if (this.isUpdating) return;
    this.isUpdating = true;
    
    try {
      const response = await fetch('/cart/change.js', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          id: key,
          quantity: quantity
        })
      });
      
      const cart = await response.json();
      await this.refreshCartHTML();
      this.updateCartCount(cart.item_count);
      
    } catch (error) {
      console.error('Error updating quantity:', error);
      this.showError('Unable to update quantity');
    } finally {
      this.isUpdating = false;
    }
  }
  
  async removeItem(key) {
    if (this.isUpdating) return;
    this.isUpdating = true;
    
    try {
      const response = await fetch('/cart/change.js', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          id: key,
          quantity: 0
        })
      });
      
      const cart = await response.json();
      await this.refreshCartHTML();
      this.updateCartCount(cart.item_count);
      
    } catch (error) {
      console.error('Error removing item:', error);
      this.showError('Unable to remove item');
    } finally {
      this.isUpdating = false;
    }
  }
  
  async addToCart(variantId, quantity = 1) {
    if (this.isUpdating) return;
    this.isUpdating = true;
    
    try {
      const response = await fetch('/cart/add.js', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          items: [{
            id: variantId,
            quantity: quantity
          }]
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        await this.refreshCartHTML();
        this.updateCartCount();
        this.open(); // Open cart after adding
        this.showSuccess('Added to cart!');
      } else {
        throw new Error('Failed to add to cart');
      }
      
    } catch (error) {
      console.error('Error adding to cart:', error);
      this.showError('Unable to add to cart');
    } finally {
      this.isUpdating = false;
    }
  }
  
  async refreshCartHTML() {
    try {
      const response = await fetch('/?view=cart-drawer');
      const html = await response.text();
      
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');
      const newCartContent = doc.querySelector('.mini-cart-drawer').innerHTML;
      
      this.drawer.innerHTML = newCartContent;
      
    } catch (error) {
      console.error('Error refreshing cart:', error);
      // Fallback: reload the page
      window.location.reload();
    }
  }
  
  updateCartDisplay() {
    // Get current cart data
    fetch('/cart.js')
      .then(response => response.json())
      .then(cart => {
        this.updateCartCount(cart.item_count);
        this.updateShippingProgress(cart.total_price);
      })
      .catch(error => console.error('Error fetching cart:', error));
  }
  
  updateCartCount(count = null) {
    if (count === null) {
      fetch('/cart.js')
        .then(response => response.json())
        .then(cart => {
          this.setCartCount(cart.item_count);
        });
    } else {
      this.setCartCount(count);
    }
  }
  
  setCartCount(count) {
    // Update all cart count elements
    const cartCounts = document.querySelectorAll('[data-cart-count], #cart-item-count');
    cartCounts.forEach(element => {
      element.textContent = count;
    });
    
    // Show/hide cart count badge
    const badges = document.querySelectorAll('.cart-count-badge');
    badges.forEach(badge => {
      if (count > 0) {
        badge.style.display = 'flex';
        badge.textContent = count;
      } else {
        badge.style.display = 'none';
      }
    });
  }
  
  updateShippingProgress(totalPrice) {
    const freeShippingThreshold = 10000; // $100 in cents
    const remaining = Math.max(0, freeShippingThreshold - totalPrice);
    const percentage = Math.min(100, (totalPrice / freeShippingThreshold) * 100);
    
    const progressBar = document.querySelector('.shipping-progress-fill');
    const progressText = document.querySelector('.shipping-text');
    const shippingUnlocked = document.querySelector('.shipping-unlocked');
    
    if (progressBar) {
      progressBar.style.width = percentage + '%';
    }
    
    if (remaining > 0 && progressText) {
      const remainingAmount = (remaining / 100).toFixed(2);
      progressText.innerHTML = `Add <strong>$${remainingAmount}</strong> more for free shipping`;
    }
    
    if (remaining <= 0 && shippingUnlocked) {
      shippingUnlocked.style.display = 'flex';
      if (progressText) progressText.style.display = 'none';
    }
  }
  
  showSuccess(message) {
    this.showNotification(message, 'success');
  }
  
  showError(message) {
    this.showNotification(message, 'error');
  }
  
  showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `mini-cart-notification ${type}`;
    notification.textContent = message;
    
    // Style the notification
    Object.assign(notification.style, {
      position: 'fixed',
      top: '20px',
      right: '20px',
      padding: '12px 20px',
      borderRadius: '8px',
      color: 'white',
      fontWeight: '500',
      fontSize: '14px',
      zIndex: '10000',
      transform: 'translateX(100%)',
      transition: 'transform 0.3s ease',
      background: type === 'error' ? '#ef4444' : type === 'success' ? '#22c55e' : '#3b82f6'
    });
    
    document.body.appendChild(notification);
    
    // Animate in
    requestAnimationFrame(() => {
      notification.style.transform = 'translateX(0)';
    });
    
    // Remove after delay
    setTimeout(() => {
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        document.body.removeChild(notification);
      }, 300);
    }, 3000);
  }
}

// Global functions for use in HTML
function openMiniCart() {
  window.miniCart.open();
}

function closeMiniCart() {
  window.miniCart.close();
}

function updateQuantity(key, quantity) {
  window.miniCart.updateQuantity(key, quantity);
}

function removeItem(key) {
  window.miniCart.removeItem(key);
}

function addToCart(variantId, quantity = 1) {
  return window.miniCart.addToCart(variantId, quantity);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  window.miniCart = new MiniCart();
});

// Handle Add to Cart forms
document.addEventListener('submit', function(e) {
  const form = e.target;
  
  if (form.action && form.action.includes('/cart/add')) {
    e.preventDefault();
    
    const formData = new FormData(form);
    const variantId = formData.get('id');
    const quantity = parseInt(formData.get('quantity')) || 1;
    
    if (variantId) {
      addToCart(variantId, quantity);
    }
  }
});

// Add to cart buttons with AJAX
document.addEventListener('click', function(e) {
  const button = e.target.closest('[data-add-to-cart]');
  if (button) {
    e.preventDefault();
    
    const variantId = button.getAttribute('data-variant-id') || button.getAttribute('data-add-to-cart');
    const quantity = parseInt(button.getAttribute('data-quantity')) || 1;
    
    if (variantId) {
      // Update button state
      const originalText = button.textContent;
      button.textContent = 'Adding...';
      button.disabled = true;
      
      addToCart(variantId, quantity).finally(() => {
        button.textContent = originalText;
        button.disabled = false;
      });
    }
  }
});

// Export for manual initialization if needed
window.MiniCart = MiniCart;
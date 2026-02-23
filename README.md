# Twelve Boards Shopify Theme

Modern mini cart implementation for Twelve Boards store.

## Mini Cart Features

- Visual shipping progress bar ($100 threshold)
- Trust signals (free shipping, returns, secure checkout)
- BNPL messaging (Afterpay, Zip)
- Smart quantity controls
- Real-time AJAX updates
- Mobile responsive design

## Files

- `sections/mini-cart-drawer.liquid` - Mini cart section
- `assets/mini-cart.js` - Mini cart JavaScript functionality

## Installation

The mini cart is automatically included when this theme is deployed to Shopify via GitHub integration.

To complete setup:
1. Add `cart-trigger` class to your cart icon
2. Customize shipping threshold in `sections/mini-cart-drawer.liquid` (line 36)

## Customization

Edit `sections/mini-cart-drawer.liquid`:
- Line 36: Free shipping threshold (default $100)
- Line 145: Trust messages
- Line 160: BNPL providers

---

Built by Jofrey for Jamie's conversion optimization project.

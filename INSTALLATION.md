# Mini Cart Installation for Atelier New Theme Update BKP Feb05

## Files Already on GitHub ✅
- `sections/mini-cart-drawer.liquid` - Mini cart section
- `assets/mini-cart.js` - Mini cart JavaScript

## Final Step: Update theme.liquid

You need to add 2 lines to `layout/theme.liquid` in the staging theme.

### Option 1: Via Shopify Admin (Easiest - 2 minutes)

1. Go to: **Online Store → Themes**
2. Find **"Atelier New Theme Update BKP Feb05"**
3. Click **"Actions" → "Edit code"**
4. Open **`layout/theme.liquid`**
5. Find the `</body>` tag (usually near line 200-300)
6. **Add these 2 lines RIGHT BEFORE `</body>`:**

```liquid
  {% section 'mini-cart-drawer' %}
  <script src="{{ 'mini-cart.js' | asset_url }}" defer></script>
</body>
```

7. Click **Save**

### Option 2: Create GitHub PR

If you want me to create a complete theme.liquid file:
1. Export your current `layout/theme.liquid` from Shopify
2. Share it with me
3. I'll add the mini cart includes
4. Create a PR for you to review

## Update Cart Icon

After updating theme.liquid, add the cart trigger:

1. Find your cart icon/button (usually in `sections/header.liquid` or similar)
2. Add class `cart-trigger` to it

**Example:**
```html
<!-- Before -->
<a href="/cart" class="header__icon header__icon--cart">
  Cart ({{ cart.item_count }})
</a>

<!-- After -->
<a href="/cart" class="header__icon header__icon--cart cart-trigger">
  Cart ({{ cart.item_count }})
</a>
```

## Testing

1. Visit staging theme preview
2. Add item to cart
3. Click cart icon
4. Mini cart should slide in from the right

## Features You'll See

✅ Visual shipping progress bar  
✅ Trust signals (free shipping, returns, secure)  
✅ BNPL messaging (Afterpay, Zip)  
✅ Smart +/- quantity controls  
✅ Real-time updates (no page reload)  
✅ Mobile responsive  

---

**Need the exact lines?** Here they are again:
```liquid
{% section 'mini-cart-drawer' %}
<script src="{{ 'mini-cart.js' | asset_url }}" defer></script>
```

Add these right before `</body>` in `layout/theme.liquid`.

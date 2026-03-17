const fastify = require('fastify')({ logger: false });

const AUTH_TOKEN = 'hestia-bearer-token-2026';

// ── Seed Data ──

const users = [
  { id: 1, name: 'Alice Chen', email: 'alice@hestia.dev', phone: '+1-555-0101', address: '123 Main St', created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: 'Bob Kumar', email: 'bob@hestia.dev', phone: '+1-555-0102', address: '456 Oak Ave', created_at: '2026-01-15T00:00:00Z' },
  { id: 3, name: 'Carol Wu', email: 'carol@hestia.dev', phone: '+1-555-0103', address: '789 Pine Rd', created_at: '2026-02-01T00:00:00Z' },
];

const restaurants = [
  { id: 1, name: 'Dragon Palace', cuisine: 'Chinese', rating: 4.5, address: '10 Dumpling Way', is_open: true, tags: ['chinese', 'dim-sum', 'noodles'], avg_price: 18.50 },
  { id: 2, name: 'Bella Napoli', cuisine: 'Italian', rating: 4.7, address: '22 Pasta Lane', is_open: true, tags: ['italian', 'pizza', 'pasta'], avg_price: 22.00 },
  { id: 3, name: 'Spice Route', cuisine: 'Indian', rating: 4.3, address: '33 Curry St', is_open: true, tags: ['indian', 'curry', 'tandoori'], avg_price: 16.00 },
  { id: 4, name: 'Sakura Sushi', cuisine: 'Japanese', rating: 4.8, address: '44 Sashimi Blvd', is_open: true, tags: ['japanese', 'sushi', 'ramen'], avg_price: 28.00 },
  { id: 5, name: 'El Fuego', cuisine: 'Mexican', rating: 4.1, address: '55 Taco Terrace', is_open: false, tags: ['mexican', 'tacos', 'burritos'], avg_price: 14.00 },
  { id: 6, name: 'Le Petit Bistro', cuisine: 'French', rating: 4.6, address: '66 Croissant Ct', is_open: true, tags: ['french', 'bistro', 'wine'], avg_price: 35.00 },
  { id: 7, name: 'Seoul Kitchen', cuisine: 'Korean', rating: 4.4, address: '77 Kimchi Ave', is_open: true, tags: ['korean', 'bbq', 'kimchi'], avg_price: 20.00 },
  { id: 8, name: 'The Burger Joint', cuisine: 'American', rating: 4.0, address: '88 Patty Pl', is_open: true, tags: ['american', 'burgers', 'fries'], avg_price: 15.00 },
];

const menuItems = [];
const menuData = {
  1: [
    ['Kung Pao Chicken', 'Spicy diced chicken with peanuts', 16.99, 'mains', 650],
    ['Pork Dumplings (8pc)', 'Steamed pork and chive dumplings', 10.99, 'appetizers', 420],
    ['Mapo Tofu', 'Silken tofu in spicy bean sauce', 14.99, 'mains', 380],
    ['Fried Rice', 'Egg fried rice with vegetables', 12.99, 'sides', 520],
    ['Hot & Sour Soup', 'Traditional Sichuan soup', 8.99, 'soups', 180],
    ['Spring Rolls (4pc)', 'Crispy vegetable spring rolls', 7.99, 'appetizers', 320],
  ],
  2: [
    ['Margherita Pizza', 'Fresh mozzarella and basil', 18.99, 'pizza', 800],
    ['Spaghetti Carbonara', 'Classic Roman pasta', 16.99, 'pasta', 720],
    ['Bruschetta', 'Tomato and garlic on toasted bread', 9.99, 'appetizers', 280],
    ['Tiramisu', 'Coffee-soaked ladyfinger dessert', 10.99, 'desserts', 450],
    ['Risotto ai Funghi', 'Mushroom risotto with truffle oil', 19.99, 'mains', 580],
    ['Caesar Salad', 'Romaine, croutons, parmesan', 12.99, 'salads', 350],
  ],
  3: [
    ['Butter Chicken', 'Creamy tomato curry with tender chicken', 17.99, 'mains', 580],
    ['Garlic Naan (2pc)', 'Freshly baked garlic bread', 4.99, 'breads', 320],
    ['Samosa (3pc)', 'Crispy potato and pea pastry', 6.99, 'appetizers', 360],
    ['Chicken Tikka Masala', 'Grilled chicken in masala sauce', 18.99, 'mains', 620],
    ['Dal Makhani', 'Slow-cooked black lentils', 13.99, 'mains', 340],
    ['Mango Lassi', 'Sweet yogurt mango drink', 5.99, 'drinks', 220],
  ],
  4: [
    ['Salmon Nigiri (4pc)', 'Fresh Atlantic salmon', 14.99, 'sushi', 280],
    ['Dragon Roll (8pc)', 'Shrimp tempura with avocado', 18.99, 'rolls', 450],
    ['Miso Ramen', 'Rich pork broth with chashu', 16.99, 'ramen', 680],
    ['Edamame', 'Steamed soybeans with sea salt', 6.99, 'appetizers', 180],
    ['Tuna Sashimi (6pc)', 'Premium bluefin tuna', 22.99, 'sashimi', 180],
    ['Matcha Ice Cream', 'Green tea ice cream', 7.99, 'desserts', 240],
  ],
  5: [
    ['Carne Asada Tacos (3)', 'Grilled steak tacos with cilantro', 13.99, 'tacos', 540],
    ['Chicken Burrito', 'Rice, beans, chicken, salsa', 12.99, 'burritos', 780],
    ['Guacamole & Chips', 'Fresh avocado dip', 8.99, 'appetizers', 380],
    ['Churros (6pc)', 'Cinnamon sugar fried dough', 7.99, 'desserts', 420],
    ['Elote', 'Grilled Mexican street corn', 5.99, 'sides', 280],
  ],
  6: [
    ['Coq au Vin', 'Braised chicken in red wine', 28.99, 'mains', 620],
    ['French Onion Soup', 'Gruyère-topped onion broth', 12.99, 'soups', 380],
    ['Crème Brûlée', 'Vanilla custard with caramel', 11.99, 'desserts', 380],
    ['Duck Confit', 'Slow-cooked duck leg', 32.99, 'mains', 720],
    ['Croissant', 'Fresh butter croissant', 4.99, 'pastries', 280],
  ],
  7: [
    ['Korean BBQ Platter', 'Bulgogi, galbi, samgyeopsal', 26.99, 'bbq', 820],
    ['Bibimbap', 'Mixed rice bowl with vegetables', 15.99, 'bowls', 580],
    ['Kimchi Jjigae', 'Spicy kimchi stew', 14.99, 'soups', 380],
    ['Tteokbokki', 'Spicy rice cakes', 11.99, 'snacks', 420],
    ['Japchae', 'Sweet potato glass noodles', 13.99, 'sides', 340],
  ],
  8: [
    ['Classic Burger', 'Angus beef, lettuce, tomato, cheese', 14.99, 'burgers', 780],
    ['Bacon Cheeseburger', 'Double patty with bacon', 17.99, 'burgers', 1020],
    ['Loaded Fries', 'Cheese, bacon, jalapeños', 9.99, 'sides', 680],
    ['Milkshake', 'Vanilla, chocolate, or strawberry', 7.99, 'drinks', 480],
    ['Chicken Wings (10pc)', 'Buffalo or BBQ sauce', 13.99, 'appetizers', 720],
    ['Onion Rings', 'Beer-battered onion rings', 8.99, 'sides', 540],
  ],
};

let menuId = 1;
for (const [restId, items] of Object.entries(menuData)) {
  for (const [name, desc, price, cat, cals] of items) {
    menuItems.push({
      id: menuId++, restaurant_id: parseInt(restId), name, description: desc,
      price, category: cat, is_available: true, calories: cals,
    });
  }
}

const now = new Date().toISOString();
const orders = [
  { id: 1, user_id: 1, restaurant_id: 1, items: [{ menu_item_id: 1, quantity: 2 }, { menu_item_id: 2, quantity: 1 }], total: 44.97, status: 'delivered', delivery_address: '123 Main St', created_at: '2026-03-10T18:00:00Z', updated_at: now, estimated_delivery: null, driver_name: 'Dave' },
  { id: 2, user_id: 1, restaurant_id: 2, items: [{ menu_item_id: 7, quantity: 1 }], total: 18.99, status: 'delivered', delivery_address: '123 Main St', created_at: '2026-03-12T19:30:00Z', updated_at: now, estimated_delivery: null, driver_name: 'Eve' },
  { id: 3, user_id: 2, restaurant_id: 4, items: [{ menu_item_id: 19, quantity: 2 }, { menu_item_id: 21, quantity: 1 }], total: 46.97, status: 'delivered', delivery_address: '456 Oak Ave', created_at: '2026-03-14T20:00:00Z', updated_at: now, estimated_delivery: null, driver_name: 'Frank' },
];
let nextOrderId = 4;

const reviews = [
  { id: 1, user_id: 1, restaurant_id: 1, order_id: 1, rating: 5, comment: 'Amazing dumplings, will order again!', created_at: '2026-03-10T20:00:00Z' },
  { id: 2, user_id: 1, restaurant_id: 2, order_id: 2, rating: 4, comment: 'Great pizza, delivery was a bit slow', created_at: '2026-03-12T21:00:00Z' },
  { id: 3, user_id: 2, restaurant_id: 4, order_id: 3, rating: 5, comment: 'Best sushi in town!', created_at: '2026-03-14T22:00:00Z' },
];
let nextReviewId = 4;

const promotions = [
  { id: 1, restaurant_id: 1, title: 'Dragon Palace Lunch Special', description: '20% off all mains during lunch hours', discount_pct: 20, min_order: 25.00, promo_code: 'DRAGON20', is_active: true, starts_at: '2026-03-01T00:00:00Z', expires_at: '2026-04-01T00:00:00Z' },
  { id: 2, restaurant_id: 2, title: 'Bella Napoli Pizza Night', description: 'Buy 2 pizzas get 15% off', discount_pct: 15, min_order: 30.00, promo_code: 'PIZZA15', is_active: true, starts_at: '2026-03-10T00:00:00Z', expires_at: '2026-03-31T00:00:00Z' },
  { id: 3, restaurant_id: 4, title: 'Sakura Sushi Happy Hour', description: '25% off sushi rolls after 5pm', discount_pct: 25, min_order: 20.00, promo_code: 'SUSHI25', is_active: true, starts_at: '2026-03-01T00:00:00Z', expires_at: '2026-03-25T00:00:00Z' },
  { id: 4, restaurant_id: 6, title: 'Le Petit Weekend Brunch', description: '10% off weekend orders over $50', discount_pct: 10, min_order: 50.00, promo_code: 'BRUNCH10', is_active: true, starts_at: '2026-03-15T00:00:00Z', expires_at: '2026-04-15T00:00:00Z' },
  { id: 5, restaurant_id: 7, title: 'Seoul Kitchen BBQ Feast', description: 'Free delivery on BBQ platters', discount_pct: 0, min_order: 40.00, promo_code: 'BBQFREE', is_active: false, starts_at: '2026-02-01T00:00:00Z', expires_at: '2026-03-01T00:00:00Z' },
  { id: 6, restaurant_id: 3, title: 'Spice Route New Customer', description: '30% off first order', discount_pct: 30, min_order: 15.00, promo_code: 'SPICE30', is_active: true, starts_at: '2026-03-01T00:00:00Z', expires_at: '2026-06-01T00:00:00Z' },
  { id: 7, restaurant_id: 8, title: 'Burger Joint Combo Deal', description: 'Free fries with any burger', discount_pct: 0, min_order: 14.99, promo_code: 'FREEFRIED', is_active: true, starts_at: '2026-03-10T00:00:00Z', expires_at: '2026-03-20T00:00:00Z' },
];

const carts = {}; // userId -> cart
let nextCartId = 1;

// ── Auth ──

function authenticate(request, reply) {
  const auth = request.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    reply.code(401).send({ error: 'Unauthorized' });
    return null;
  }
  if (auth.slice(7) !== AUTH_TOKEN) {
    reply.code(401).send({ error: 'Invalid token' });
    return null;
  }
  return 1; // User ID 1
}

// ── Health ──

fastify.get('/api/health', async () => ({ status: 'ok', app: 'hestia-eats' }));

// ── Restaurants ──

fastify.get('/api/restaurants', async (request) => {
  const { cuisine, search, open, limit = '20', offset = '0' } = request.query;
  const lim = Math.min(Math.max(parseInt(limit) || 20, 1), 100);
  const off = Math.max(parseInt(offset) || 0, 0);

  let filtered = restaurants.filter(r => {
    if (cuisine && r.cuisine.toLowerCase() !== cuisine.toLowerCase()) return false;
    if (search) {
      const s = search.toLowerCase();
      if (!r.name.toLowerCase().includes(s) && !r.cuisine.toLowerCase().includes(s)) return false;
    }
    if (open === 'true' && !r.is_open) return false;
    return true;
  });

  const total = filtered.length;
  return { restaurants: filtered.slice(off, off + lim), total, limit: lim, offset: off };
});

fastify.get('/api/restaurants/:id', async (request, reply) => {
  const r = restaurants.find(r => r.id === parseInt(request.params.id));
  if (!r) return reply.code(404).send({ error: 'Restaurant not found' });
  return r;
});

fastify.get('/api/restaurants/:id/menu', async (request, reply) => {
  const restId = parseInt(request.params.id);
  if (!restaurants.find(r => r.id === restId)) {
    return reply.code(404).send({ error: 'Restaurant not found' });
  }
  const { category } = request.query;
  let items = menuItems.filter(m => m.restaurant_id === restId);
  if (category) items = items.filter(m => m.category.toLowerCase() === category.toLowerCase());
  return { restaurant_id: restId, items, total: items.length };
});

fastify.get('/api/restaurants/:id/reviews', async (request) => {
  const restId = parseInt(request.params.id);
  const revs = reviews.filter(r => r.restaurant_id === restId);
  const avg = revs.length ? Math.round(revs.reduce((s, r) => s + r.rating, 0) / revs.length * 10) / 10 : 0;
  return { restaurant_id: restId, reviews: revs, total: revs.length, average_rating: avg };
});

// ── Menu Items ──

fastify.get('/api/menu/:id', async (request, reply) => {
  const item = menuItems.find(m => m.id === parseInt(request.params.id));
  if (!item) return reply.code(404).send({ error: 'Menu item not found' });
  return item;
});

// ── Cart ──

fastify.get('/api/cart', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const cart = carts[userId];
  if (!cart) return { items: [], total: 0 };
  return cart;
});

fastify.post('/api/cart/items', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const { menu_item_id, quantity } = request.body;
  if (!quantity || quantity <= 0) return reply.code(400).send({ error: 'Quantity must be positive' });
  if (quantity > 20) return reply.code(400).send({ error: 'Maximum 20 items per menu item' });

  const menuItem = menuItems.find(m => m.id === menu_item_id);
  if (!menuItem) return reply.code(404).send({ error: 'Menu item not found' });
  if (!menuItem.is_available) return reply.code(400).send({ error: 'Menu item is not available' });

  if (!carts[userId]) {
    carts[userId] = {
      id: ++nextCartId, user_id: userId, restaurant_id: menuItem.restaurant_id,
      items: [], total: 0, created_at: new Date().toISOString(),
    };
  }
  const cart = carts[userId];
  if (cart.restaurant_id !== menuItem.restaurant_id && cart.items.length > 0) {
    return reply.code(400).send({ error: 'Cart already has items from a different restaurant. Clear cart first.' });
  }
  cart.restaurant_id = menuItem.restaurant_id;

  const existing = cart.items.find(i => i.menu_item_id === menu_item_id);
  if (existing) { existing.quantity += quantity; }
  else { cart.items.push({ menu_item_id, quantity }); }

  cart.total = Math.round(cart.items.reduce((sum, ci) => {
    const mi = menuItems.find(m => m.id === ci.menu_item_id);
    return sum + (mi ? mi.price * ci.quantity : 0);
  }, 0) * 100) / 100;

  return cart;
});

fastify.delete('/api/cart', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  delete carts[userId];
  return { message: 'Cart cleared' };
});

// ── Orders ──

fastify.post('/api/orders', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const { delivery_address } = request.body;
  if (!delivery_address) return reply.code(400).send({ error: 'Delivery address is required' });

  const cart = carts[userId];
  if (!cart || !cart.items.length) return reply.code(400).send({ error: 'Cart is empty' });

  const now = new Date().toISOString();
  const order = {
    id: nextOrderId++, user_id: userId, restaurant_id: cart.restaurant_id,
    items: [...cart.items], total: cart.total, status: 'pending',
    delivery_address, created_at: now, updated_at: now,
    estimated_delivery: new Date(Date.now() + 45 * 60000).toISOString(),
    driver_name: null,
  };
  orders.push(order);
  delete carts[userId];
  reply.code(201);
  return order;
});

fastify.get('/api/orders', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const { status, limit = '20', offset = '0' } = request.query;
  const lim = Math.min(Math.max(parseInt(limit) || 20, 1), 100);
  const off = Math.max(parseInt(offset) || 0, 0);

  let userOrders = orders.filter(o => o.user_id === userId);
  if (status) userOrders = userOrders.filter(o => o.status === status);
  const total = userOrders.length;
  return { orders: userOrders.slice(off, off + lim), total, limit: lim, offset: off };
});

fastify.get('/api/orders/:id', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const order = orders.find(o => o.id === parseInt(request.params.id) && o.user_id === userId);
  if (!order) return reply.code(404).send({ error: 'Order not found' });
  return order;
});

fastify.patch('/api/orders/:id/status', async (request, reply) => {
  const { status, driver_name } = request.body;
  const valid = ['confirmed', 'preparing', 'delivering', 'delivered', 'cancelled'];
  if (!valid.includes(status)) {
    return reply.code(400).send({ error: `Invalid status. Must be one of: ${valid.join(', ')}` });
  }
  const order = orders.find(o => o.id === parseInt(request.params.id));
  if (!order) return reply.code(404).send({ error: 'Order not found' });

  order.status = status;
  order.updated_at = new Date().toISOString();
  if (driver_name) order.driver_name = driver_name;
  return order;
});

fastify.get('/api/orders/:id/tracking', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const orderId = parseInt(request.params.id);
  const order = orders.find(o => o.id === orderId && o.user_id === userId);
  if (!order) return reply.code(404).send({ error: 'Order not found' });

  if (order.status !== 'delivering' && order.status !== 'delivered') {
    return { order_id: orderId, status: order.status, message: 'Tracking available once order is out for delivery' };
  }
  return {
    order_id: orderId, status: order.status, driver_name: order.driver_name || '',
    driver_phone: '+1-555-0200', eta: order.estimated_delivery || '',
    latitude: 37.7749 + orderId * 0.001, longitude: -122.4194 + orderId * 0.001,
    updated_at: order.updated_at,
  };
});

// ── Reviews ──

fastify.post('/api/reviews', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const { restaurant_id, order_id, rating, comment } = request.body;
  if (!rating || rating < 1 || rating > 5) return reply.code(400).send({ error: 'Rating must be between 1 and 5' });
  if (!comment) return reply.code(400).send({ error: 'Comment is required' });

  const order = orders.find(o => o.id === order_id && o.user_id === userId && o.restaurant_id === restaurant_id);
  if (!order) return reply.code(404).send({ error: 'Order not found or not eligible for review' });
  if (order.status !== 'delivered') return reply.code(400).send({ error: 'Can only review delivered orders' });
  if (reviews.find(r => r.order_id === order_id && r.user_id === userId)) {
    return reply.code(409).send({ error: 'You already reviewed this order' });
  }

  const review = {
    id: nextReviewId++, user_id: userId, restaurant_id, order_id,
    rating, comment, created_at: new Date().toISOString(),
  };
  reviews.push(review);

  // Update restaurant rating
  const restReviews = reviews.filter(r => r.restaurant_id === restaurant_id);
  const avg = Math.round(restReviews.reduce((s, r) => s + r.rating, 0) / restReviews.length * 10) / 10;
  const rest = restaurants.find(r => r.id === restaurant_id);
  if (rest) rest.rating = avg;

  reply.code(201);
  return review;
});

// ── User Profile ──

fastify.get('/api/user/profile', async (request, reply) => {
  const userId = authenticate(request, reply);
  if (!userId) return;
  const user = users.find(u => u.id === userId);
  if (!user) return reply.code(404).send({ error: 'User not found' });

  const userOrders = orders.filter(o => o.user_id === userId);
  const totalSpent = Math.round(userOrders.reduce((s, o) => s + o.total, 0) * 100) / 100;
  return { user, order_count: userOrders.length, total_spent: totalSpent, member_since: user.created_at };
});

// ── Search ──

fastify.get('/api/search', async (request, reply) => {
  const { q } = request.query;
  if (!q) return reply.code(400).send({ error: "Search query 'q' is required" });
  const ql = q.toLowerCase();

  const seen = new Set();
  const matchedRests = [];
  for (const r of restaurants) {
    if (seen.has(r.id)) continue;
    if (r.name.toLowerCase().includes(ql) || r.cuisine.toLowerCase().includes(ql) || r.tags.some(t => t.includes(ql))) {
      seen.add(r.id);
      matchedRests.push(r);
    }
  }
  const matchedItems = menuItems.filter(m =>
    m.name.toLowerCase().includes(ql) || m.description.toLowerCase().includes(ql) || m.category.toLowerCase().includes(ql)
  );
  return { query: q, restaurants: matchedRests, menu_items: matchedItems };
});

// ── Promotions ──

fastify.get('/api/promotions', async (request) => {
  const { active = 'true', restaurant_id } = request.query;
  const restIdFilter = restaurant_id ? parseInt(restaurant_id) : null;

  const result = [];
  for (const promo of promotions) {
    if (active !== 'false' && !promo.is_active) continue;
    if (restIdFilter !== null && promo.restaurant_id !== restIdFilter) continue;
    // N+1: fetch restaurant details for each promotion
    const entry = { ...promo };
    for (const rest of restaurants) {
      if (rest.id === promo.restaurant_id) {
        entry.restaurant_name = rest.name;
        entry.restaurant_cuisine = rest.cuisine;
        entry.restaurant_rating = rest.rating;
        break;
      }
    }
    result.push(entry);
  }
  return { promotions: result, total: result.length };
});

fastify.get('/api/promotions/:id', async (request, reply) => {
  const promo = promotions.find(p => p.id === parseInt(request.params.id));
  if (!promo) return reply.code(404).send({ error: 'Promotion not found' });

  const entry = { ...promo };
  const rest = restaurants.find(r => r.id === promo.restaurant_id);
  if (rest) entry.restaurant = rest;
  entry.menu_items = menuItems.filter(m => m.restaurant_id === promo.restaurant_id && m.is_available);
  entry.menu_item_count = entry.menu_items.length;
  return entry;
});

// ── Start ──

const start = async () => {
  try {
    await fastify.listen({ port: 8080, host: '0.0.0.0' });
    console.log(`Hestia Eats starting on :8080`);
    console.log(`Endpoints: 20 | Restaurants: ${restaurants.length} | Menu items: ${menuItems.length} | Promotions: ${promotions.length}`);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
};

start();

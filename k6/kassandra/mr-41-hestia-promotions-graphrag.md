## GraphRAG Traversal

Graph: 164 nodes, 180 edges
Matched endpoints: 17

  ● GET /api/orders/{order_id}
    ├─ RETURNS → Order (schema)
    │  ├─ .id: integer
    │  ├─ .user_id: integer
    │  ├─ .restaurant_id: integer
    │  ├─ .items: array<CartItem>
    │  └─ REFERENCES → CartItem
    │     ├─ .menu_item_id: integer
    │     ├─ .quantity: integer
    │  ├─ .total: number
    │  ├─ .status: string
    │  ├─ .delivery_address: string
    │  ├─ .created_at: string
    │  ├─ .updated_at: string
    │  ├─ .estimated_delivery: string
    │  ├─ .driver_name: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → order_id (path)
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● GET /api/restaurants/{restaurant_id}/reviews
    ├─ RETURNS → ReviewListResponse (schema)
    │  ├─ .restaurant_id: integer
    │  ├─ .reviews: array<Review>
    │  └─ REFERENCES → Review
    │     ├─ .id: integer
    │     ├─ .user_id: integer
    │     ├─ .restaurant_id: integer
    │     ├─ .order_id: integer
    │     ├─ .rating: integer
    │     ├─ .comment: string
    │     ├─ .created_at: string
    │  ├─ .total: integer
    │  ├─ .average_rating: number
    ├─ HAS_PARAM → restaurant_id (path)

  ● GET /api/search
    ├─ RETURNS → SearchResponse (schema)
    │  ├─ .query: string
    │  ├─ .restaurants: array<Restaurant>
    │  └─ REFERENCES → Restaurant
    │     ├─ .id: integer
    │     ├─ .name: string
    │     ├─ .cuisine: string
    │     ├─ .rating: number
    │     ├─ .address: string
    │     ├─ .is_open: boolean
    │     ├─ .tags: array
    │     ├─ .avg_price: number
    │  ├─ .menu_items: array<MenuItem>
    │  └─ REFERENCES → MenuItem
    │     ├─ .id: integer
    │     ├─ .restaurant_id: integer
    │     ├─ .name: string
    │     ├─ .description: string
    │     ├─ .price: number
    │     ├─ .category: string
    │     ├─ .is_available: boolean
    │     ├─ .calories: integer
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → q (query)

  ● GET /api/user/profile
    ├─ RETURNS → UserProfile (schema)
    │  ├─ .user: object
    │  ├─ .order_count: integer
    │  ├─ .total_spent: number
    │  ├─ .member_since: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● DELETE /api/cart
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● GET /api/promotions
    ├─ RETURNS → PromotionListResponse (schema)
    │  ├─ .promotions: array<Promotion>
    │  └─ REFERENCES → Promotion
    │     ├─ .id: integer
    │     ├─ .restaurant_id: integer
    │     ├─ .title: string
    │     ├─ .description: string
    │     ├─ .discount_pct: number
    │     ├─ .min_order: number
    │     ├─ .promo_code: string
    │     ├─ .is_active: boolean
    │     ├─ .starts_at: string
    │     ├─ .expires_at: string
    │     ├─ .restaurant_name: string
    │     ├─ .restaurant_cuisine: string
    │     ├─ .restaurant_rating: number
    │  ├─ .total: integer
    ├─ HAS_PARAM → active (query)
    ├─ HAS_PARAM → restaurant_id (query)

  ● GET /api/health
    ├─ RETURNS → HealthResponse (schema)
    │  ├─ .status: string
    │  ├─ .app: string

  ● POST /api/reviews
    ├─ ACCEPTS → CreateReviewRequest (schema)
    │  ├─ .restaurant_id: integer
    │  ├─ .order_id: integer
    │  ├─ .rating: integer
    │  ├─ .comment: string
    ├─ RETURNS → Review (schema)
    │  ├─ .id: integer
    │  ├─ .user_id: integer
    │  ├─ .restaurant_id: integer
    │  ├─ .order_id: integer
    │  ├─ .rating: integer
    │  ├─ .comment: string
    │  ├─ .created_at: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● GET /api/promotions/{promotion_id}
    ├─ RETURNS → PromotionDetail (schema)
    │  └─ REFERENCES → Promotion
    │     ├─ .id: integer
    │     ├─ .restaurant_id: integer
    │     ├─ .title: string
    │     ├─ .description: string
    │     ├─ .discount_pct: number
    │     ├─ .min_order: number
    │     ├─ .promo_code: string
    │     ├─ .is_active: boolean
    │     ├─ .starts_at: string
    │     ├─ .expires_at: string
    │     ├─ .restaurant_name: string
    │     ├─ .restaurant_cuisine: string
    │     ├─ .restaurant_rating: number
    │  ├─ .restaurant: $ref:Restaurant
    │  └─ REFERENCES → Restaurant
    │     ├─ .id: integer
    │     ├─ .name: string
    │     ├─ .cuisine: string
    │     ├─ .rating: number
    │     ├─ .address: string
    │     ├─ .is_open: boolean
    │     ├─ .tags: array
    │     ├─ .avg_price: number
    │  ├─ .menu_items: array<MenuItem>
    │  └─ REFERENCES → MenuItem
    │     ├─ .id: integer
    │     ├─ .restaurant_id: integer
    │     ├─ .name: string
    │     ├─ .description: string
    │     ├─ .price: number
    │     ├─ .category: string
    │     ├─ .is_available: boolean
    │     ├─ .calories: integer
    │  ├─ .menu_item_count: integer
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → promotion_id (path)

  ● PATCH /api/orders/{order_id}/status
    ├─ ACCEPTS → UpdateStatusRequest (schema)
    │  ├─ .status: string
    │  ├─ .driver_name: string
    ├─ RETURNS → Order (schema)
    │  ├─ .id: integer
    │  ├─ .user_id: integer
    │  ├─ .restaurant_id: integer
    │  ├─ .items: array<CartItem>
    │  └─ REFERENCES → CartItem
    │     ├─ .menu_item_id: integer
    │     ├─ .quantity: integer
    │  ├─ .total: number
    │  ├─ .status: string
    │  ├─ .delivery_address: string
    │  ├─ .created_at: string
    │  ├─ .updated_at: string
    │  ├─ .estimated_delivery: string
    │  ├─ .driver_name: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → order_id (path)

  ● GET /api/menu/{item_id}
    ├─ RETURNS → MenuItem (schema)
    │  ├─ .id: integer
    │  ├─ .restaurant_id: integer
    │  ├─ .name: string
    │  ├─ .description: string
    │  ├─ .price: number
    │  ├─ .category: string
    │  ├─ .is_available: boolean
    │  ├─ .calories: integer
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → item_id (path)

  ● GET /api/restaurants/{restaurant_id}
    ├─ RETURNS → Restaurant (schema)
    │  ├─ .id: integer
    │  ├─ .name: string
    │  ├─ .cuisine: string
    │  ├─ .rating: number
    │  ├─ .address: string
    │  ├─ .is_open: boolean
    │  ├─ .tags: array
    │  ├─ .avg_price: number
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → restaurant_id (path)

  ● GET /api/orders/{order_id}/tracking
    ├─ RETURNS → DeliveryStatus (schema)
    │  ├─ .order_id: integer
    │  ├─ .status: string
    │  ├─ .driver_name: string
    │  ├─ .driver_phone: string
    │  ├─ .eta: string
    │  ├─ .latitude: number
    │  ├─ .longitude: number
    │  ├─ .updated_at: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → order_id (path)
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● GET /api/restaurants
    ├─ RETURNS → RestaurantListResponse (schema)
    │  ├─ .restaurants: array<Restaurant>
    │  └─ REFERENCES → Restaurant
    │     ├─ .id: integer
    │     ├─ .name: string
    │     ├─ .cuisine: string
    │     ├─ .rating: number
    │     ├─ .address: string
    │     ├─ .is_open: boolean
    │     ├─ .tags: array
    │     ├─ .avg_price: number
    │  ├─ .total: integer
    │  ├─ .limit: integer
    │  ├─ .offset: integer
    ├─ HAS_PARAM → cuisine (query)
    ├─ HAS_PARAM → search (query)
    ├─ HAS_PARAM → open (query)
    ├─ HAS_PARAM → limit (query)
    ├─ HAS_PARAM → offset (query)

  ● POST /api/cart/items
    ├─ ACCEPTS → AddToCartRequest (schema)
    │  ├─ .menu_item_id: integer
    │  ├─ .quantity: integer
    ├─ RETURNS → Cart (schema)
    │  ├─ .id: integer
    │  ├─ .user_id: integer
    │  ├─ .restaurant_id: integer
    │  ├─ .items: array<CartItem>
    │  └─ REFERENCES → CartItem
    │     ├─ .menu_item_id: integer
    │     ├─ .quantity: integer
    │  ├─ .total: number
    │  ├─ .created_at: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● POST /api/orders
    ├─ ACCEPTS → CreateOrderRequest (schema)
    │  ├─ .delivery_address: string
    ├─ RETURNS → Order (schema)
    │  ├─ .id: integer
    │  ├─ .user_id: integer
    │  ├─ .restaurant_id: integer
    │  ├─ .items: array<CartItem>
    │  └─ REFERENCES → CartItem
    │     ├─ .menu_item_id: integer
    │     ├─ .quantity: integer
    │  ├─ .total: number
    │  ├─ .status: string
    │  ├─ .delivery_address: string
    │  ├─ .created_at: string
    │  ├─ .updated_at: string
    │  ├─ .estimated_delivery: string
    │  ├─ .driver_name: string
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ REQUIRES_AUTH → security:BearerAuth (security)

  ● GET /api/restaurants/{restaurant_id}/menu
    ├─ RETURNS → MenuResponse (schema)
    │  ├─ .restaurant_id: integer
    │  ├─ .items: array<MenuItem>
    │  └─ REFERENCES → MenuItem
    │     ├─ .id: integer
    │     ├─ .restaurant_id: integer
    │     ├─ .name: string
    │     ├─ .description: string
    │     ├─ .price: number
    │     ├─ .category: string
    │     ├─ .is_available: boolean
    │     ├─ .calories: integer
    │  ├─ .total: integer
    ├─ RETURNS → Error (schema)
    │  ├─ .error: string
    ├─ HAS_PARAM → restaurant_id (path)
    ├─ HAS_PARAM → category (query)

Retrieved: 21 schemas, 17 params, auth=yes

---

## GET /api/orders/{order_id}
Summary: Get order details
## GET /api/restaurants/{restaurant_id}/reviews
Summary: Get reviews for a restaurant
## GET /api/search
Summary: Search restaurants and menu items
## GET /api/user/profile
Summary: Get current user's profile with order stats
## DELETE /api/cart
Summary: Clear the cart
## GET /api/promotions
Summary: List promotions with restaurant enrichment (N+1 pattern)
## GET /api/health
Summary: Health check
## POST /api/reviews
Summary: Submit a review for a delivered order
## GET /api/promotions/{promotion_id}
Summary: Get promotion detail with restaurant and menu items
## PATCH /api/orders/{order_id}/status
Summary: Update order status (admin/driver)
## GET /api/menu/{item_id}
Summary: Get a single menu item by ID
## GET /api/restaurants/{restaurant_id}
Summary: Get restaurant by ID
## GET /api/orders/{order_id}/tracking
Summary: Get live delivery tracking for an order
## GET /api/restaurants
Summary: List restaurants with filtering and pagination
## POST /api/cart/items
Summary: Add item to cart
## POST /api/orders
Summary: Create order from cart
## GET /api/restaurants/{restaurant_id}/menu
Summary: Get restaurant menu items

Authentication: Bearer token required

Parameters:
  - order_id: integer in path (required)
  - restaurant_id: integer in path (required)
  - q: string in query (required)
  - active: string in query
  - restaurant_id: integer in query
  - promotion_id: integer in path (required)
  - order_id: integer in path (required)
  - item_id: integer in path (required)
  - restaurant_id: integer in path (required)
  - order_id: integer in path (required)
  - cuisine: string in query
  - search: string in query
  - open: string in query
  - limit: integer in query
  - offset: integer in query
  - restaurant_id: integer in path (required)
  - category: string in query

Schemas:

### CartItem
  - menu_item_id: integer *
  - quantity: integer *

### Order
  - id: integer *
  - user_id: integer *
  - restaurant_id: integer *
  - items: array<CartItem> *
  - total: number *
  - status: string *
  - delivery_address: string
  - created_at: string
  - updated_at: string
  - estimated_delivery: string
  - driver_name: string

### Error
  - error: string

### Review
  - id: integer *
  - user_id: integer *
  - restaurant_id: integer *
  - order_id: integer *
  - rating: integer *
  - comment: string *
  - created_at: string

### ReviewListResponse
  - restaurant_id: integer *
  - reviews: array<Review> *
  - total: integer *
  - average_rating: number *

### Restaurant
  - id: integer *
  - name: string *
  - cuisine: string *
  - rating: number *
  - address: string
  - is_open: boolean *
  - tags: array
  - avg_price: number

### MenuItem
  - id: integer *
  - restaurant_id: integer *
  - name: string *
  - description: string
  - price: number *
  - category: string *
  - is_available: boolean *
  - calories: integer

### SearchResponse
  - query: string *
  - restaurants: array<Restaurant> *
  - menu_items: array<MenuItem> *

### UserProfile
  - user: object *
  - order_count: integer *
  - total_spent: number *
  - member_since: string

### Promotion
  - id: integer *
  - restaurant_id: integer *
  - title: string *
  - description: string
  - discount_pct: number *
  - min_order: number
  - promo_code: string
  - is_active: boolean *
  - starts_at: string
  - expires_at: string
  - restaurant_name: string
  - restaurant_cuisine: string
  - restaurant_rating: number

### PromotionListResponse
  - promotions: array<Promotion> *
  - total: integer *

### HealthResponse
  - status: string
  - app: string

### CreateReviewRequest
  - restaurant_id: integer *
  - order_id: integer *
  - rating: integer *
  - comment: string *

### PromotionDetail
  - restaurant: $ref:Restaurant
  - menu_items: array<MenuItem>
  - menu_item_count: integer

### UpdateStatusRequest
  - status: string *
  - driver_name: string

### DeliveryStatus
  - order_id: integer *
  - status: string *
  - driver_name: string
  - driver_phone: string
  - eta: string
  - latitude: number
  - longitude: number
  - updated_at: string

### RestaurantListResponse
  - restaurants: array<Restaurant> *
  - total: integer *
  - limit: integer
  - offset: integer

### AddToCartRequest
  - menu_item_id: integer *
  - quantity: integer *

### Cart
  - id: integer *
  - user_id: integer *
  - restaurant_id: integer *
  - items: array<CartItem> *
  - total: number *
  - created_at: string

### CreateOrderRequest
  - delivery_address: string *

### MenuResponse
  - restaurant_id: integer *
  - items: array<MenuItem> *
  - total: integer *

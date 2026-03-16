package main

import (
	"encoding/json"
	"fmt"
	"log"
	"math"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// ── Models ──

type Restaurant struct {
	ID       int      `json:"id"`
	Name     string   `json:"name"`
	Cuisine  string   `json:"cuisine"`
	Rating   float64  `json:"rating"`
	Address  string   `json:"address"`
	IsOpen   bool     `json:"is_open"`
	Tags     []string `json:"tags"`
	AvgPrice float64  `json:"avg_price"`
}

type MenuItem struct {
	ID           int     `json:"id"`
	RestaurantID int     `json:"restaurant_id"`
	Name         string  `json:"name"`
	Description  string  `json:"description"`
	Price        float64 `json:"price"`
	Category     string  `json:"category"`
	IsAvailable  bool    `json:"is_available"`
	Calories     int     `json:"calories"`
}

type CartItem struct {
	MenuItemID int `json:"menu_item_id"`
	Quantity   int `json:"quantity"`
}

type Cart struct {
	ID           int        `json:"id"`
	UserID       int        `json:"user_id"`
	RestaurantID int        `json:"restaurant_id"`
	Items        []CartItem `json:"items"`
	Total        float64    `json:"total"`
	CreatedAt    string     `json:"created_at"`
}

type Order struct {
	ID           int        `json:"id"`
	UserID       int        `json:"user_id"`
	RestaurantID int        `json:"restaurant_id"`
	Items        []CartItem `json:"items"`
	Total        float64    `json:"total"`
	Status       string     `json:"status"` // pending, confirmed, preparing, delivering, delivered, cancelled
	DeliveryAddr string     `json:"delivery_address"`
	CreatedAt    string     `json:"created_at"`
	UpdatedAt    string     `json:"updated_at"`
	EstDelivery  string     `json:"estimated_delivery,omitempty"`
	DriverName   string     `json:"driver_name,omitempty"`
}

type Review struct {
	ID           int    `json:"id"`
	UserID       int    `json:"user_id"`
	RestaurantID int    `json:"restaurant_id"`
	OrderID      int    `json:"order_id"`
	Rating       int    `json:"rating"` // 1-5
	Comment      string `json:"comment"`
	CreatedAt    string `json:"created_at"`
}

type User struct {
	ID        int    `json:"id"`
	Name      string `json:"name"`
	Email     string `json:"email"`
	Phone     string `json:"phone"`
	Address   string `json:"address"`
	CreatedAt string `json:"created_at"`
}

type DeliveryStatus struct {
	OrderID     int     `json:"order_id"`
	Status      string  `json:"status"`
	DriverName  string  `json:"driver_name"`
	DriverPhone string  `json:"driver_phone"`
	ETA         string  `json:"eta"`
	Lat         float64 `json:"latitude"`
	Lng         float64 `json:"longitude"`
	UpdatedAt   string  `json:"updated_at"`
}

// ── In-memory store ──

type Store struct {
	mu          sync.RWMutex
	restaurants []Restaurant
	menuItems   []MenuItem
	carts       map[int]*Cart // userID -> cart
	orders      []Order
	reviews     []Review
	users       []User
	nextOrderID int
	nextReview  int
	nextCartID  int
	token       string // simple auth token
}

func NewStore() *Store {
	s := &Store{
		carts:       make(map[int]*Cart),
		nextOrderID: 1,
		nextReview:  1,
		nextCartID:  1,
		token:       "hestia-bearer-token-2026",
	}
	s.seed()
	return s
}

func (s *Store) seed() {
	s.users = []User{
		{ID: 1, Name: "Alice Chen", Email: "alice@hestia.dev", Phone: "+1-555-0101", Address: "123 Main St", CreatedAt: "2026-01-01T00:00:00Z"},
		{ID: 2, Name: "Bob Kumar", Email: "bob@hestia.dev", Phone: "+1-555-0102", Address: "456 Oak Ave", CreatedAt: "2026-01-15T00:00:00Z"},
		{ID: 3, Name: "Carol Wu", Email: "carol@hestia.dev", Phone: "+1-555-0103", Address: "789 Pine Rd", CreatedAt: "2026-02-01T00:00:00Z"},
	}

	s.restaurants = []Restaurant{
		{ID: 1, Name: "Dragon Palace", Cuisine: "Chinese", Rating: 4.5, Address: "10 Dumpling Way", IsOpen: true, Tags: []string{"chinese", "dim-sum", "noodles"}, AvgPrice: 18.50},
		{ID: 2, Name: "Bella Napoli", Cuisine: "Italian", Rating: 4.7, Address: "22 Pasta Lane", IsOpen: true, Tags: []string{"italian", "pizza", "pasta"}, AvgPrice: 22.00},
		{ID: 3, Name: "Spice Route", Cuisine: "Indian", Rating: 4.3, Address: "33 Curry St", IsOpen: true, Tags: []string{"indian", "curry", "tandoori"}, AvgPrice: 16.00},
		{ID: 4, Name: "Sakura Sushi", Cuisine: "Japanese", Rating: 4.8, Address: "44 Sashimi Blvd", IsOpen: true, Tags: []string{"japanese", "sushi", "ramen"}, AvgPrice: 28.00},
		{ID: 5, Name: "El Fuego", Cuisine: "Mexican", Rating: 4.1, Address: "55 Taco Terrace", IsOpen: false, Tags: []string{"mexican", "tacos", "burritos"}, AvgPrice: 14.00},
		{ID: 6, Name: "Le Petit Bistro", Cuisine: "French", Rating: 4.6, Address: "66 Croissant Ct", IsOpen: true, Tags: []string{"french", "bistro", "wine"}, AvgPrice: 35.00},
		{ID: 7, Name: "Seoul Kitchen", Cuisine: "Korean", Rating: 4.4, Address: "77 Kimchi Ave", IsOpen: true, Tags: []string{"korean", "bbq", "kimchi"}, AvgPrice: 20.00},
		{ID: 8, Name: "The Burger Joint", Cuisine: "American", Rating: 4.0, Address: "88 Patty Pl", IsOpen: true, Tags: []string{"american", "burgers", "fries"}, AvgPrice: 15.00},
	}

	menuID := 1
	menuData := map[int][]struct {
		name     string
		desc     string
		price    float64
		cat      string
		calories int
	}{
		1: {
			{"Kung Pao Chicken", "Spicy diced chicken with peanuts", 16.99, "mains", 650},
			{"Pork Dumplings (8pc)", "Steamed pork and chive dumplings", 10.99, "appetizers", 420},
			{"Mapo Tofu", "Silken tofu in spicy bean sauce", 14.99, "mains", 380},
			{"Fried Rice", "Egg fried rice with vegetables", 12.99, "sides", 520},
			{"Hot & Sour Soup", "Traditional Sichuan soup", 8.99, "soups", 180},
			{"Spring Rolls (4pc)", "Crispy vegetable spring rolls", 7.99, "appetizers", 320},
		},
		2: {
			{"Margherita Pizza", "Fresh mozzarella and basil", 18.99, "pizza", 800},
			{"Spaghetti Carbonara", "Classic Roman pasta", 16.99, "pasta", 720},
			{"Bruschetta", "Tomato and garlic on toasted bread", 9.99, "appetizers", 280},
			{"Tiramisu", "Coffee-soaked ladyfinger dessert", 10.99, "desserts", 450},
			{"Risotto ai Funghi", "Mushroom risotto with truffle oil", 19.99, "mains", 580},
			{"Caesar Salad", "Romaine, croutons, parmesan", 12.99, "salads", 350},
		},
		3: {
			{"Butter Chicken", "Creamy tomato curry with tender chicken", 17.99, "mains", 580},
			{"Garlic Naan (2pc)", "Freshly baked garlic bread", 4.99, "breads", 320},
			{"Samosa (3pc)", "Crispy potato and pea pastry", 6.99, "appetizers", 360},
			{"Chicken Tikka Masala", "Grilled chicken in masala sauce", 18.99, "mains", 620},
			{"Dal Makhani", "Slow-cooked black lentils", 13.99, "mains", 340},
			{"Mango Lassi", "Sweet yogurt mango drink", 5.99, "drinks", 220},
		},
		4: {
			{"Salmon Nigiri (4pc)", "Fresh Atlantic salmon", 14.99, "sushi", 280},
			{"Dragon Roll (8pc)", "Shrimp tempura with avocado", 18.99, "rolls", 450},
			{"Miso Ramen", "Rich pork broth with chashu", 16.99, "ramen", 680},
			{"Edamame", "Steamed soybeans with sea salt", 6.99, "appetizers", 180},
			{"Tuna Sashimi (6pc)", "Premium bluefin tuna", 22.99, "sashimi", 180},
			{"Matcha Ice Cream", "Green tea ice cream", 7.99, "desserts", 240},
		},
		5: {
			{"Carne Asada Tacos (3)", "Grilled steak tacos with cilantro", 13.99, "tacos", 540},
			{"Chicken Burrito", "Rice, beans, chicken, salsa", 12.99, "burritos", 780},
			{"Guacamole & Chips", "Fresh avocado dip", 8.99, "appetizers", 380},
			{"Churros (6pc)", "Cinnamon sugar fried dough", 7.99, "desserts", 420},
			{"Elote", "Grilled Mexican street corn", 5.99, "sides", 280},
		},
		6: {
			{"Coq au Vin", "Braised chicken in red wine", 28.99, "mains", 620},
			{"French Onion Soup", "Gruyère-topped onion broth", 12.99, "soups", 380},
			{"Crème Brûlée", "Vanilla custard with caramel", 11.99, "desserts", 380},
			{"Duck Confit", "Slow-cooked duck leg", 32.99, "mains", 720},
			{"Croissant", "Fresh butter croissant", 4.99, "pastries", 280},
		},
		7: {
			{"Korean BBQ Platter", "Bulgogi, galbi, samgyeopsal", 26.99, "bbq", 820},
			{"Bibimbap", "Mixed rice bowl with vegetables", 15.99, "bowls", 580},
			{"Kimchi Jjigae", "Spicy kimchi stew", 14.99, "soups", 380},
			{"Tteokbokki", "Spicy rice cakes", 11.99, "snacks", 420},
			{"Japchae", "Sweet potato glass noodles", 13.99, "sides", 340},
		},
		8: {
			{"Classic Burger", "Angus beef, lettuce, tomato, cheese", 14.99, "burgers", 780},
			{"Bacon Cheeseburger", "Double patty with bacon", 17.99, "burgers", 1020},
			{"Loaded Fries", "Cheese, bacon, jalapeños", 9.99, "sides", 680},
			{"Milkshake", "Vanilla, chocolate, or strawberry", 7.99, "drinks", 480},
			{"Chicken Wings (10pc)", "Buffalo or BBQ sauce", 13.99, "appetizers", 720},
			{"Onion Rings", "Beer-battered onion rings", 8.99, "sides", 540},
		},
	}

	for restID, items := range menuData {
		for _, item := range items {
			s.menuItems = append(s.menuItems, MenuItem{
				ID:           menuID,
				RestaurantID: restID,
				Name:         item.name,
				Description:  item.desc,
				Price:        item.price,
				Category:     item.cat,
				IsAvailable:  true,
				Calories:     item.calories,
			})
			menuID++
		}
	}

	// Seed some orders and reviews
	now := time.Now().UTC().Format(time.RFC3339)
	s.orders = []Order{
		{ID: 1, UserID: 1, RestaurantID: 1, Items: []CartItem{{MenuItemID: 1, Quantity: 2}, {MenuItemID: 2, Quantity: 1}}, Total: 44.97, Status: "delivered", DeliveryAddr: "123 Main St", CreatedAt: "2026-03-10T18:00:00Z", UpdatedAt: now, DriverName: "Dave"},
		{ID: 2, UserID: 1, RestaurantID: 2, Items: []CartItem{{MenuItemID: 7, Quantity: 1}}, Total: 18.99, Status: "delivered", DeliveryAddr: "123 Main St", CreatedAt: "2026-03-12T19:30:00Z", UpdatedAt: now, DriverName: "Eve"},
		{ID: 3, UserID: 2, RestaurantID: 4, Items: []CartItem{{MenuItemID: 19, Quantity: 2}, {MenuItemID: 21, Quantity: 1}}, Total: 46.97, Status: "delivered", DeliveryAddr: "456 Oak Ave", CreatedAt: "2026-03-14T20:00:00Z", UpdatedAt: now, DriverName: "Frank"},
	}
	s.nextOrderID = 4

	s.reviews = []Review{
		{ID: 1, UserID: 1, RestaurantID: 1, OrderID: 1, Rating: 5, Comment: "Amazing dumplings, will order again!", CreatedAt: "2026-03-10T20:00:00Z"},
		{ID: 2, UserID: 1, RestaurantID: 2, OrderID: 2, Rating: 4, Comment: "Great pizza, delivery was a bit slow", CreatedAt: "2026-03-12T21:00:00Z"},
		{ID: 3, UserID: 2, RestaurantID: 4, OrderID: 3, Rating: 5, Comment: "Best sushi in town!", CreatedAt: "2026-03-14T22:00:00Z"},
	}
	s.nextReview = 4
}

// ── Helpers ──

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}

func (s *Store) authenticate(r *http.Request) (int, bool) {
	auth := r.Header.Get("Authorization")
	if !strings.HasPrefix(auth, "Bearer ") {
		return 0, false
	}
	token := auth[7:]
	if token != s.token {
		return 0, false
	}
	// Simple: token encodes user ID 1 by default
	return 1, true
}

func getPathParam(path string, prefix string) string {
	rest := strings.TrimPrefix(path, prefix)
	parts := strings.SplitN(rest, "/", 2)
	if len(parts) > 0 {
		return parts[0]
	}
	return ""
}

func getIntParam(path string, prefix string) (int, bool) {
	s := getPathParam(path, prefix)
	id, err := strconv.Atoi(s)
	return id, err == nil
}

// ── Handlers ──

func (s *Store) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, 200, map[string]string{"status": "ok", "app": "hestia-eats"})
}

// GET /api/restaurants
func (s *Store) handleListRestaurants(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	cuisine := r.URL.Query().Get("cuisine")
	search := strings.ToLower(r.URL.Query().Get("search"))
	openOnly := r.URL.Query().Get("open") == "true"
	limitStr := r.URL.Query().Get("limit")
	offsetStr := r.URL.Query().Get("offset")
	limit := 20
	offset := 0
	if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 100 {
		limit = l
	}
	if o, err := strconv.Atoi(offsetStr); err == nil && o >= 0 {
		offset = o
	}

	var filtered []Restaurant
	for _, r := range s.restaurants {
		if cuisine != "" && !strings.EqualFold(r.Cuisine, cuisine) {
			continue
		}
		if search != "" && !strings.Contains(strings.ToLower(r.Name), search) && !strings.Contains(strings.ToLower(r.Cuisine), search) {
			continue
		}
		if openOnly && !r.IsOpen {
			continue
		}
		filtered = append(filtered, r)
	}

	total := len(filtered)
	if offset >= len(filtered) {
		filtered = nil
	} else {
		end := offset + limit
		if end > len(filtered) {
			end = len(filtered)
		}
		filtered = filtered[offset:end]
	}

	writeJSON(w, 200, map[string]interface{}{
		"restaurants": filtered,
		"total":       total,
		"limit":       limit,
		"offset":      offset,
	})
}

// GET /api/restaurants/{id}
func (s *Store) handleGetRestaurant(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	id, ok := getIntParam(r.URL.Path, "/api/restaurants/")
	if !ok {
		writeError(w, 400, "Invalid restaurant ID")
		return
	}
	for _, rest := range s.restaurants {
		if rest.ID == id {
			writeJSON(w, 200, rest)
			return
		}
	}
	writeError(w, 404, "Restaurant not found")
}

// GET /api/restaurants/{id}/menu
func (s *Store) handleGetMenu(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// Parse: /api/restaurants/{id}/menu
	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/restaurants/"), "/")
	if len(parts) < 2 {
		writeError(w, 400, "Invalid path")
		return
	}
	restID, err := strconv.Atoi(parts[0])
	if err != nil {
		writeError(w, 400, "Invalid restaurant ID")
		return
	}

	category := r.URL.Query().Get("category")
	var items []MenuItem
	for _, item := range s.menuItems {
		if item.RestaurantID != restID {
			continue
		}
		if category != "" && !strings.EqualFold(item.Category, category) {
			continue
		}
		items = append(items, item)
	}

	// Check restaurant exists
	found := false
	for _, rest := range s.restaurants {
		if rest.ID == restID {
			found = true
			break
		}
	}
	if !found {
		writeError(w, 404, "Restaurant not found")
		return
	}

	writeJSON(w, 200, map[string]interface{}{
		"restaurant_id": restID,
		"items":         items,
		"total":         len(items),
	})
}

// GET /api/restaurants/{id}/reviews
func (s *Store) handleGetRestaurantReviews(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/restaurants/"), "/")
	if len(parts) < 2 {
		writeError(w, 400, "Invalid path")
		return
	}
	restID, err := strconv.Atoi(parts[0])
	if err != nil {
		writeError(w, 400, "Invalid restaurant ID")
		return
	}

	var reviews []Review
	for _, rev := range s.reviews {
		if rev.RestaurantID == restID {
			reviews = append(reviews, rev)
		}
	}

	// Compute average
	avg := 0.0
	if len(reviews) > 0 {
		sum := 0
		for _, rev := range reviews {
			sum += rev.Rating
		}
		avg = math.Round(float64(sum)/float64(len(reviews))*10) / 10
	}

	writeJSON(w, 200, map[string]interface{}{
		"restaurant_id":  restID,
		"reviews":        reviews,
		"total":          len(reviews),
		"average_rating": avg,
	})
}

// GET /api/menu/{id}
func (s *Store) handleGetMenuItem(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	id, ok := getIntParam(r.URL.Path, "/api/menu/")
	if !ok {
		writeError(w, 400, "Invalid menu item ID")
		return
	}
	for _, item := range s.menuItems {
		if item.ID == id {
			writeJSON(w, 200, item)
			return
		}
	}
	writeError(w, 404, "Menu item not found")
}

// GET /api/cart
func (s *Store) handleGetCart(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	cart, exists := s.carts[userID]
	if !exists {
		writeJSON(w, 200, map[string]interface{}{
			"items": []CartItem{},
			"total": 0,
		})
		return
	}
	writeJSON(w, 200, cart)
}

// POST /api/cart/items
func (s *Store) handleAddToCart(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	var req struct {
		MenuItemID int `json:"menu_item_id"`
		Quantity   int `json:"quantity"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "Invalid request body")
		return
	}
	if req.Quantity <= 0 {
		writeError(w, 400, "Quantity must be positive")
		return
	}
	if req.Quantity > 20 {
		writeError(w, 400, "Maximum 20 items per menu item")
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	// Find menu item
	var menuItem *MenuItem
	for i := range s.menuItems {
		if s.menuItems[i].ID == req.MenuItemID {
			menuItem = &s.menuItems[i]
			break
		}
	}
	if menuItem == nil {
		writeError(w, 404, "Menu item not found")
		return
	}
	if !menuItem.IsAvailable {
		writeError(w, 400, "Menu item is not available")
		return
	}

	cart, exists := s.carts[userID]
	if !exists {
		s.nextCartID++
		cart = &Cart{
			ID:           s.nextCartID,
			UserID:       userID,
			RestaurantID: menuItem.RestaurantID,
			Items:        []CartItem{},
			CreatedAt:    time.Now().UTC().Format(time.RFC3339),
		}
		s.carts[userID] = cart
	}

	// Can only order from one restaurant at a time
	if cart.RestaurantID != menuItem.RestaurantID && len(cart.Items) > 0 {
		writeError(w, 400, "Cart already has items from a different restaurant. Clear cart first.")
		return
	}
	cart.RestaurantID = menuItem.RestaurantID

	// Update quantity if already in cart, otherwise add
	found := false
	for i := range cart.Items {
		if cart.Items[i].MenuItemID == req.MenuItemID {
			cart.Items[i].Quantity += req.Quantity
			found = true
			break
		}
	}
	if !found {
		cart.Items = append(cart.Items, CartItem{MenuItemID: req.MenuItemID, Quantity: req.Quantity})
	}

	// Recalculate total
	cart.Total = 0
	for _, ci := range cart.Items {
		for _, mi := range s.menuItems {
			if mi.ID == ci.MenuItemID {
				cart.Total += mi.Price * float64(ci.Quantity)
				break
			}
		}
	}
	cart.Total = math.Round(cart.Total*100) / 100

	writeJSON(w, 200, cart)
}

// DELETE /api/cart
func (s *Store) handleClearCart(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	delete(s.carts, userID)
	writeJSON(w, 200, map[string]string{"message": "Cart cleared"})
}

// POST /api/orders
func (s *Store) handleCreateOrder(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	var req struct {
		DeliveryAddress string `json:"delivery_address"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "Invalid request body")
		return
	}
	if req.DeliveryAddress == "" {
		writeError(w, 400, "Delivery address is required")
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	cart, exists := s.carts[userID]
	if !exists || len(cart.Items) == 0 {
		writeError(w, 400, "Cart is empty")
		return
	}

	now := time.Now().UTC().Format(time.RFC3339)
	order := Order{
		ID:           s.nextOrderID,
		UserID:       userID,
		RestaurantID: cart.RestaurantID,
		Items:        make([]CartItem, len(cart.Items)),
		Total:        cart.Total,
		Status:       "pending",
		DeliveryAddr: req.DeliveryAddress,
		CreatedAt:    now,
		UpdatedAt:    now,
		EstDelivery:  time.Now().Add(45 * time.Minute).UTC().Format(time.RFC3339),
	}
	copy(order.Items, cart.Items)
	s.nextOrderID++
	s.orders = append(s.orders, order)

	// Clear cart after order
	delete(s.carts, userID)

	writeJSON(w, 201, order)
}

// GET /api/orders
func (s *Store) handleListOrders(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	status := r.URL.Query().Get("status")
	limitStr := r.URL.Query().Get("limit")
	offsetStr := r.URL.Query().Get("offset")
	limit := 20
	offset := 0
	if l, err := strconv.Atoi(limitStr); err == nil && l > 0 && l <= 100 {
		limit = l
	}
	if o, err := strconv.Atoi(offsetStr); err == nil && o >= 0 {
		offset = o
	}

	var orders []Order
	for _, o := range s.orders {
		if o.UserID != userID {
			continue
		}
		if status != "" && o.Status != status {
			continue
		}
		orders = append(orders, o)
	}

	total := len(orders)
	if offset >= len(orders) {
		orders = nil
	} else {
		end := offset + limit
		if end > len(orders) {
			end = len(orders)
		}
		orders = orders[offset:end]
	}

	writeJSON(w, 200, map[string]interface{}{
		"orders": orders,
		"total":  total,
		"limit":  limit,
		"offset": offset,
	})
}

// GET /api/orders/{id}
func (s *Store) handleGetOrder(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	id, ok := getIntParam(r.URL.Path, "/api/orders/")
	if !ok {
		writeError(w, 400, "Invalid order ID")
		return
	}

	for _, o := range s.orders {
		if o.ID == id && o.UserID == userID {
			writeJSON(w, 200, o)
			return
		}
	}
	writeError(w, 404, "Order not found")
}

// PATCH /api/orders/{id}/status
func (s *Store) handleUpdateOrderStatus(w http.ResponseWriter, r *http.Request) {
	// In production, this would be admin/driver only
	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/orders/"), "/")
	if len(parts) < 2 {
		writeError(w, 400, "Invalid path")
		return
	}
	orderID, err := strconv.Atoi(parts[0])
	if err != nil {
		writeError(w, 400, "Invalid order ID")
		return
	}

	var req struct {
		Status     string `json:"status"`
		DriverName string `json:"driver_name,omitempty"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "Invalid request body")
		return
	}

	validStatuses := map[string]bool{
		"confirmed": true, "preparing": true, "delivering": true,
		"delivered": true, "cancelled": true,
	}
	if !validStatuses[req.Status] {
		writeError(w, 400, "Invalid status. Must be one of: confirmed, preparing, delivering, delivered, cancelled")
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	for i := range s.orders {
		if s.orders[i].ID == orderID {
			s.orders[i].Status = req.Status
			s.orders[i].UpdatedAt = time.Now().UTC().Format(time.RFC3339)
			if req.DriverName != "" {
				s.orders[i].DriverName = req.DriverName
			}
			writeJSON(w, 200, s.orders[i])
			return
		}
	}
	writeError(w, 404, "Order not found")
}

// GET /api/orders/{id}/tracking
func (s *Store) handleOrderTracking(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/orders/"), "/")
	if len(parts) < 2 {
		writeError(w, 400, "Invalid path")
		return
	}
	orderID, err := strconv.Atoi(parts[0])
	if err != nil {
		writeError(w, 400, "Invalid order ID")
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, o := range s.orders {
		if o.ID == orderID && o.UserID == userID {
			if o.Status != "delivering" && o.Status != "delivered" {
				writeJSON(w, 200, map[string]interface{}{
					"order_id": orderID,
					"status":   o.Status,
					"message":  "Tracking available once order is out for delivery",
				})
				return
			}
			tracking := DeliveryStatus{
				OrderID:     orderID,
				Status:      o.Status,
				DriverName:  o.DriverName,
				DriverPhone: "+1-555-0200",
				ETA:         o.EstDelivery,
				Lat:         37.7749 + float64(orderID)*0.001,
				Lng:         -122.4194 + float64(orderID)*0.001,
				UpdatedAt:   o.UpdatedAt,
			}
			writeJSON(w, 200, tracking)
			return
		}
	}
	writeError(w, 404, "Order not found")
}

// POST /api/reviews
func (s *Store) handleCreateReview(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	var req struct {
		RestaurantID int    `json:"restaurant_id"`
		OrderID      int    `json:"order_id"`
		Rating       int    `json:"rating"`
		Comment      string `json:"comment"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeError(w, 400, "Invalid request body")
		return
	}
	if req.Rating < 1 || req.Rating > 5 {
		writeError(w, 400, "Rating must be between 1 and 5")
		return
	}
	if req.Comment == "" {
		writeError(w, 400, "Comment is required")
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	// Verify order exists and belongs to user
	orderFound := false
	for _, o := range s.orders {
		if o.ID == req.OrderID && o.UserID == userID && o.RestaurantID == req.RestaurantID {
			if o.Status != "delivered" {
				writeError(w, 400, "Can only review delivered orders")
				s.mu.Unlock()
				return
			}
			orderFound = true
			break
		}
	}
	if !orderFound {
		writeError(w, 404, "Order not found or not eligible for review")
		return
	}

	// Check for duplicate review
	for _, rev := range s.reviews {
		if rev.OrderID == req.OrderID && rev.UserID == userID {
			writeError(w, 409, "You already reviewed this order")
			return
		}
	}

	review := Review{
		ID:           s.nextReview,
		UserID:       userID,
		RestaurantID: req.RestaurantID,
		OrderID:      req.OrderID,
		Rating:       req.Rating,
		Comment:      req.Comment,
		CreatedAt:    time.Now().UTC().Format(time.RFC3339),
	}
	s.nextReview++
	s.reviews = append(s.reviews, review)

	// Update restaurant rating
	var ratings []int
	for _, rev := range s.reviews {
		if rev.RestaurantID == req.RestaurantID {
			ratings = append(ratings, rev.Rating)
		}
	}
	if len(ratings) > 0 {
		sum := 0
		for _, r := range ratings {
			sum += r
		}
		for i := range s.restaurants {
			if s.restaurants[i].ID == req.RestaurantID {
				s.restaurants[i].Rating = math.Round(float64(sum)/float64(len(ratings))*10) / 10
				break
			}
		}
	}

	writeJSON(w, 201, review)
}

// GET /api/user/profile
func (s *Store) handleGetProfile(w http.ResponseWriter, r *http.Request) {
	userID, ok := s.authenticate(r)
	if !ok {
		writeError(w, 401, "Unauthorized")
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	for _, u := range s.users {
		if u.ID == userID {
			// Count orders
			orderCount := 0
			totalSpent := 0.0
			for _, o := range s.orders {
				if o.UserID == userID {
					orderCount++
					totalSpent += o.Total
				}
			}
			writeJSON(w, 200, map[string]interface{}{
				"user":         u,
				"order_count":  orderCount,
				"total_spent":  math.Round(totalSpent*100) / 100,
				"member_since": u.CreatedAt,
			})
			return
		}
	}
	writeError(w, 404, "User not found")
}

// GET /api/search
func (s *Store) handleSearch(w http.ResponseWriter, r *http.Request) {
	q := strings.ToLower(r.URL.Query().Get("q"))
	if q == "" {
		writeError(w, 400, "Search query 'q' is required")
		return
	}

	s.mu.RLock()
	defer s.mu.RUnlock()

	var restaurants []Restaurant
	var menuItems []MenuItem

	for _, rest := range s.restaurants {
		if strings.Contains(strings.ToLower(rest.Name), q) ||
			strings.Contains(strings.ToLower(rest.Cuisine), q) {
			restaurants = append(restaurants, rest)
		}
		for _, tag := range rest.Tags {
			if strings.Contains(tag, q) {
				restaurants = append(restaurants, rest)
				break
			}
		}
	}

	for _, item := range s.menuItems {
		if strings.Contains(strings.ToLower(item.Name), q) ||
			strings.Contains(strings.ToLower(item.Description), q) ||
			strings.Contains(strings.ToLower(item.Category), q) {
			menuItems = append(menuItems, item)
		}
	}

	// Deduplicate restaurants
	seen := make(map[int]bool)
	var uniqueRests []Restaurant
	for _, r := range restaurants {
		if !seen[r.ID] {
			seen[r.ID] = true
			uniqueRests = append(uniqueRests, r)
		}
	}

	writeJSON(w, 200, map[string]interface{}{
		"query":       q,
		"restaurants": uniqueRests,
		"menu_items":  menuItems,
	})
}

// ── Router ──

func (s *Store) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path

	switch {
	case path == "/api/health" && r.Method == "GET":
		s.handleHealth(w, r)

	case path == "/api/restaurants" && r.Method == "GET":
		s.handleListRestaurants(w, r)

	case strings.HasPrefix(path, "/api/restaurants/") && strings.HasSuffix(path, "/menu") && r.Method == "GET":
		s.handleGetMenu(w, r)

	case strings.HasPrefix(path, "/api/restaurants/") && strings.HasSuffix(path, "/reviews") && r.Method == "GET":
		s.handleGetRestaurantReviews(w, r)

	case strings.HasPrefix(path, "/api/restaurants/") && r.Method == "GET":
		s.handleGetRestaurant(w, r)

	case strings.HasPrefix(path, "/api/menu/") && r.Method == "GET":
		s.handleGetMenuItem(w, r)

	case path == "/api/cart" && r.Method == "GET":
		s.handleGetCart(w, r)

	case path == "/api/cart/items" && r.Method == "POST":
		s.handleAddToCart(w, r)

	case path == "/api/cart" && r.Method == "DELETE":
		s.handleClearCart(w, r)

	case path == "/api/orders" && r.Method == "POST":
		s.handleCreateOrder(w, r)

	case path == "/api/orders" && r.Method == "GET":
		s.handleListOrders(w, r)

	case strings.HasPrefix(path, "/api/orders/") && strings.HasSuffix(path, "/status") && r.Method == "PATCH":
		s.handleUpdateOrderStatus(w, r)

	case strings.HasPrefix(path, "/api/orders/") && strings.HasSuffix(path, "/tracking") && r.Method == "GET":
		s.handleOrderTracking(w, r)

	case strings.HasPrefix(path, "/api/orders/") && r.Method == "GET":
		s.handleGetOrder(w, r)

	case path == "/api/reviews" && r.Method == "POST":
		s.handleCreateReview(w, r)

	case path == "/api/user/profile" && r.Method == "GET":
		s.handleGetProfile(w, r)

	case path == "/api/search" && r.Method == "GET":
		s.handleSearch(w, r)

	default:
		writeError(w, 404, "Not found")
	}
}

func main() {
	store := NewStore()
	port := "8080"
	fmt.Printf("Hestia Eats starting on :%s\n", port)
	fmt.Printf("Endpoints: 18 | Restaurants: %d | Menu items: %d\n", len(store.restaurants), len(store.menuItems))
	log.Fatal(http.ListenAndServe(":"+port, store))
}

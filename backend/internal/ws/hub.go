// Package ws implements a topic-based WebSocket hub that fans messages out to
// subscribed clients. Quote updates arrive both from the local ingestion loop
// and (across replicas) from the Redis "quotes" pub/sub channel.
package ws

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

// Message is the envelope sent to clients.
type Message struct {
	Topic string `json:"topic"`
	Data  any    `json:"data"`
}

// clientMsg is what clients send to subscribe/unsubscribe.
type clientMsg struct {
	Action string   `json:"action"` // "subscribe" | "unsubscribe"
	Topics []string `json:"topics"`
}

// Client is a single WebSocket connection.
type Client struct {
	conn   *websocket.Conn
	send   chan []byte
	topics map[string]struct{}
	mu     sync.Mutex
}

// Hub maintains the set of clients and their topic subscriptions.
type Hub struct {
	mu      sync.RWMutex
	clients map[*Client]struct{}
	log     *slog.Logger
	up      websocket.Upgrader
}

// NewHub creates a hub. allowOrigin decides which Origins may connect.
func NewHub(log *slog.Logger, allowOrigin func(r *http.Request) bool) *Hub {
	return &Hub{
		clients: make(map[*Client]struct{}),
		log:     log,
		up: websocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
			CheckOrigin:     allowOrigin,
		},
	}
}

// Broadcast sends data to every client subscribed to topic.
func (h *Hub) Broadcast(topic string, data any) {
	payload, err := json.Marshal(Message{Topic: topic, Data: data})
	if err != nil {
		return
	}
	h.mu.RLock()
	defer h.mu.RUnlock()
	for c := range h.clients {
		c.mu.Lock()
		_, subscribed := c.topics[topic]
		c.mu.Unlock()
		if !subscribed {
			continue
		}
		select {
		case c.send <- payload:
		default: // drop for slow consumers to protect the hub
		}
	}
}

// ServeHTTP upgrades the connection and runs the read/write pumps.
func (h *Hub) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	conn, err := h.up.Upgrade(w, r, nil)
	if err != nil {
		h.log.Warn("ws upgrade failed", "err", err)
		return
	}
	c := &Client{
		conn:   conn,
		send:   make(chan []byte, 256),
		topics: make(map[string]struct{}),
	}
	h.mu.Lock()
	h.clients[c] = struct{}{}
	h.mu.Unlock()

	go h.writePump(c)
	h.readPump(c)
}

func (h *Hub) readPump(c *Client) {
	defer func() {
		h.mu.Lock()
		delete(h.clients, c)
		h.mu.Unlock()
		close(c.send)
		_ = c.conn.Close()
	}()

	c.conn.SetReadLimit(4096)
	_ = c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	c.conn.SetPongHandler(func(string) error {
		return c.conn.SetReadDeadline(time.Now().Add(60 * time.Second))
	})

	for {
		_, raw, err := c.conn.ReadMessage()
		if err != nil {
			return
		}
		var msg clientMsg
		if err := json.Unmarshal(raw, &msg); err != nil {
			continue
		}
		c.mu.Lock()
		switch msg.Action {
		case "subscribe":
			for _, t := range msg.Topics {
				c.topics[t] = struct{}{}
			}
		case "unsubscribe":
			for _, t := range msg.Topics {
				delete(c.topics, t)
			}
		}
		c.mu.Unlock()
	}
}

func (h *Hub) writePump(c *Client) {
	ticker := time.NewTicker(25 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case payload, ok := <-c.send:
			_ = c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if !ok {
				_ = c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.conn.WriteMessage(websocket.TextMessage, payload); err != nil {
				return
			}
		case <-ticker.C:
			_ = c.conn.SetWriteDeadline(time.Now().Add(10 * time.Second))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

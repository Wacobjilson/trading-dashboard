// Package httpapi wires the chi router, REST handlers, auth, and the WebSocket
// endpoint together.
package httpapi

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/jackc/pgx/v5/pgconn"

	"github.com/quanta/trading-dashboard/backend/internal/auth"
	"github.com/quanta/trading-dashboard/backend/internal/cache"
	"github.com/quanta/trading-dashboard/backend/internal/market"
	"github.com/quanta/trading-dashboard/backend/internal/models"
	"github.com/quanta/trading-dashboard/backend/internal/store"
	"github.com/quanta/trading-dashboard/backend/internal/ws"
)

// Server holds dependencies for HTTP handlers.
type Server struct {
	store    *store.Store
	cache    *cache.Cache
	auth     *auth.Manager
	provider market.Provider
	hub      *ws.Hub
	log      *slog.Logger
}

// NewServer constructs the HTTP server dependencies.
func NewServer(st *store.Store, c *cache.Cache, am *auth.Manager, p market.Provider, hub *ws.Hub, log *slog.Logger) *Server {
	return &Server{store: st, cache: c, auth: am, provider: p, hub: hub, log: log}
}

// Router builds the chi router with all routes registered.
func (s *Server) Router(allowedOrigins []string) http.Handler {
	r := chi.NewRouter()
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP)
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(30 * time.Second))
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   allowedOrigins,
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"Authorization", "Content-Type"},
		AllowCredentials: false,
		MaxAge:           300,
	}))

	r.Get("/healthz", s.handleHealth)
	r.Get("/readyz", s.handleReady)

	r.Route("/api/v1", func(r chi.Router) {
		// Public auth routes.
		r.Post("/auth/register", s.handleRegister)
		r.Post("/auth/login", s.handleLogin)

		// Public reference data.
		r.Get("/instruments", s.handleInstruments)

		// Protected routes.
		r.Group(func(r chi.Router) {
			r.Use(s.auth.Middleware)
			r.Get("/me", s.handleMe)
			r.Get("/quotes", s.handleQuotes)
		})
	})

	// WebSocket (auth via ?token=, enforced by middleware).
	r.With(s.auth.Middleware).Get("/ws", func(w http.ResponseWriter, req *http.Request) {
		s.hub.ServeHTTP(w, req)
	})

	return r
}

// ─── helpers ─────────────────────────────────────────────────────────────────

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func writeErr(w http.ResponseWriter, status int, msg string) {
	writeJSON(w, status, map[string]string{"error": msg})
}

// ─── health ──────────────────────────────────────────────────────────────────

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *Server) handleReady(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if err := s.cache.Raw().Ping(ctx).Err(); err != nil {
		writeErr(w, http.StatusServiceUnavailable, "cache not ready")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready", "provider": s.provider.Name()})
}

// ─── auth ────────────────────────────────────────────────────────────────────

type registerReq struct {
	Email       string `json:"email"`
	Password    string `json:"password"`
	DisplayName string `json:"displayName"`
}

type authResp struct {
	Token string      `json:"token"`
	User  models.User `json:"user"`
}

func (s *Server) handleRegister(w http.ResponseWriter, r *http.Request) {
	var req registerReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid body")
		return
	}
	req.Email = strings.ToLower(strings.TrimSpace(req.Email))
	if !strings.Contains(req.Email, "@") || len(req.Password) < 8 {
		writeErr(w, http.StatusBadRequest, "email required and password must be >= 8 chars")
		return
	}

	// Basic per-IP rate limit on registration.
	if ok, _ := s.cache.AllowN(r.Context(), "rl:register:"+ipOf(r), 10, time.Minute); !ok {
		writeErr(w, http.StatusTooManyRequests, "slow down")
		return
	}

	hash, err := auth.HashPassword(req.Password)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "hash error")
		return
	}
	u, err := s.store.CreateUser(r.Context(), req.Email, req.DisplayName, hash)
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23505" {
			writeErr(w, http.StatusConflict, "email already registered")
			return
		}
		s.log.Error("create user", "err", err)
		writeErr(w, http.StatusInternalServerError, "could not create user")
		return
	}
	token, err := s.auth.Issue(u.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "token error")
		return
	}
	writeJSON(w, http.StatusCreated, authResp{Token: token, User: u})
}

type loginReq struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

func (s *Server) handleLogin(w http.ResponseWriter, r *http.Request) {
	var req loginReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeErr(w, http.StatusBadRequest, "invalid body")
		return
	}
	req.Email = strings.ToLower(strings.TrimSpace(req.Email))

	if ok, _ := s.cache.AllowN(r.Context(), "rl:login:"+ipOf(r), 20, time.Minute); !ok {
		writeErr(w, http.StatusTooManyRequests, "slow down")
		return
	}

	u, err := s.store.UserByEmail(r.Context(), req.Email)
	if err != nil || !auth.VerifyPassword(req.Password, u.PasswordHash) {
		// Constant-ish response to avoid user enumeration.
		writeErr(w, http.StatusUnauthorized, "invalid credentials")
		return
	}
	token, err := s.auth.Issue(u.ID)
	if err != nil {
		writeErr(w, http.StatusInternalServerError, "token error")
		return
	}
	writeJSON(w, http.StatusOK, authResp{Token: token, User: u})
}

func (s *Server) handleMe(w http.ResponseWriter, r *http.Request) {
	uid := auth.UserID(r.Context())
	// Single-user mode: the local user has no DB row; return a synthetic profile.
	if uid == auth.LocalUserID {
		writeJSON(w, http.StatusOK, models.User{
			ID:          auth.LocalUserID,
			Email:       "local@quanta",
			DisplayName: "Local User",
		})
		return
	}
	u, err := s.store.UserByID(r.Context(), uid)
	if err != nil {
		writeErr(w, http.StatusNotFound, "user not found")
		return
	}
	writeJSON(w, http.StatusOK, u)
}

// ─── market data ───────────────────────────────────────────────────────────────

func (s *Server) handleInstruments(w http.ResponseWriter, _ *http.Request) {
	out := make([]models.Symbol, 0, len(market.DashboardInstruments))
	for _, in := range market.DashboardInstruments {
		out = append(out, models.Symbol{Symbol: in.Symbol, Name: in.Name, AssetClass: in.AssetClass})
	}
	writeJSON(w, http.StatusOK, out)
}

// handleQuotes returns the latest snapshot for the requested symbols (defaults
// to the full dashboard set). Reads from Postgres (kept fresh by the ingestor).
func (s *Server) handleQuotes(w http.ResponseWriter, r *http.Request) {
	symbols := parseSymbols(r.URL.Query().Get("symbols"))
	if len(symbols) == 0 {
		for _, in := range market.DashboardInstruments {
			symbols = append(symbols, in.Symbol)
		}
	}
	quotes, err := s.store.LatestQuotes(r.Context(), symbols)
	if err != nil {
		s.log.Error("latest quotes", "err", err)
		writeErr(w, http.StatusInternalServerError, "could not load quotes")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"quotes": quotes})
}

func parseSymbols(s string) []string {
	if s == "" {
		return nil
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.ToUpper(strings.TrimSpace(p)); p != "" {
			out = append(out, p)
		}
	}
	return out
}

func ipOf(r *http.Request) string {
	if ip := r.Header.Get("X-Forwarded-For"); ip != "" {
		return strings.TrimSpace(strings.Split(ip, ",")[0])
	}
	return r.RemoteAddr
}

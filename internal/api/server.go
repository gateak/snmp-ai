package api

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/akbarkhamidov/snmp-ai/internal/config"
	"github.com/akbarkhamidov/snmp-ai/internal/llm"
	"github.com/akbarkhamidov/snmp-ai/internal/mib"
	"github.com/akbarkhamidov/snmp-ai/internal/snmp"
	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
	"go.uber.org/zap"
)

type Server struct {
	config     *config.APIConfig
	logger     *zap.Logger
	echo       *echo.Echo
	snmpClient *snmp.Client
	mibManager *mib.Manager
	llmClient  *llm.Client
}

func NewServer(
	cfg *config.APIConfig,
	snmpClient *snmp.Client,
	mibManager *mib.Manager,
	llmClient *llm.Client,
	logger *zap.Logger,
) *Server {
	e := echo.New()

	// Middleware
	e.Use(middleware.Logger())
	e.Use(middleware.Recover())
	e.Use(middleware.CORS())

	server := &Server{
		config:     cfg,
		logger:     logger,
		echo:       e,
		snmpClient: snmpClient,
		mibManager: mibManager,
		llmClient:  llmClient,
	}

	// Routes
	api := e.Group("/api/v1")
	api.POST("/query", server.handleQuery)
	api.GET("/mibs", server.handleListMIBs)
	api.POST("/mibs/:name", server.handleLoadMIB)

	return server
}

func (s *Server) Start() error {
	return s.echo.Start(s.config.Host + ":" + s.config.Port)
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.echo.Shutdown(ctx)
}

func (s *Server) handleQuery(c echo.Context) error {
	var request struct {
		Query string `json:"query"`
	}

	if err := c.Bind(&request); err != nil {
		return c.JSON(http.StatusBadRequest, map[string]string{"error": "Invalid request"})
	}

	// Check cache first
	if cached, err := s.llmClient.GetCachedResponse(request.Query); err == nil {
		return c.JSON(http.StatusOK, cached)
	}

	// Interpret query using LLM
	query, err := s.llmClient.InterpretQuery(request.Query)
	if err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": "Failed to interpret query"})
	}

	// Validate operation
	if !s.llmClient.ValidateOperation(query) {
		return c.JSON(http.StatusBadRequest, map[string]string{"error": "Invalid operation"})
	}

	// Execute SNMP operation
	var results []snmp.SNMPResult
	var err error

	switch query.Operation {
	case "walk":
		results, err = s.snmpClient.Walk(query.Target, query.OIDs[0])
	case "get":
		results, err = s.snmpClient.Get(query.Target, query.OIDs)
	case "bulkwalk":
		results, err = s.snmpClient.BulkWalk(query.Target, query.OIDs[0])
	default:
		return c.JSON(http.StatusBadRequest, map[string]string{"error": "Unsupported operation"})
	}

	if err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": "SNMP operation failed"})
	}

	// Cache and return results
	response := llm.Response{
		Results: make([]llm.Result, len(results)),
	}

	for i, r := range results {
		mibInfo, _ := s.mibManager.GetOIDInfo(r.OID)
		response.Results[i] = llm.Result{
			OID:   r.OID,
			Value: r.Value,
			Info:  mibInfo.Description,
		}
	}

	if err := s.llmClient.CacheResponse(request.Query, response); err != nil {
		s.logger.Error("Failed to cache response", zap.Error(err))
	}

	return c.JSON(http.StatusOK, response)
}

func (s *Server) handleListMIBs(c echo.Context) error {
	// In a real implementation, this would list all available MIBs
	return c.JSON(http.StatusOK, map[string]interface{}{
		"mibs": []string{"IF-MIB", "SNMPv2-MIB"},
	})
}

func (s *Server) handleLoadMIB(c echo.Context) error {
	name := c.Param("name")
	if err := s.mibManager.LoadMIB(name); err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{"error": "Failed to load MIB"})
	}

	return c.JSON(http.StatusOK, map[string]string{"status": "MIB loaded successfully"})
}

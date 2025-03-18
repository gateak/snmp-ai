package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/akbarkhamidov/snmp-ai/internal/api"
	"github.com/akbarkhamidov/snmp-ai/internal/config"
	"github.com/akbarkhamidov/snmp-ai/internal/snmp"
	"github.com/akbarkhamidov/snmp-ai/internal/mib"
	"github.com/akbarkhamidov/snmp-ai/internal/llm"
	"go.uber.org/zap"
)

func main() {
	// Initialize logger
	logger, _ := zap.NewProduction()
	defer logger.Sync()

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logger.Fatal("Failed to load configuration", zap.Error(err))
	}

	// Create context with cancellation
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Initialize components
	snmpClient, err := snmp.NewClient(cfg.SNMP, logger)
	if err != nil {
		logger.Fatal("Failed to create SNMP client", zap.Error(err))
	}

	mibManager, err := mib.NewManager(cfg.MIB, &cfg.Redis, logger)
	if err != nil {
		logger.Fatal("Failed to create MIB manager", zap.Error(err))
	}

	llmClient, err := llm.NewClient(cfg.LLM, &cfg.Redis, logger)
	if err != nil {
		logger.Fatal("Failed to create LLM client", zap.Error(err))
	}

	// Initialize API server
	server := api.NewServer(cfg.API, snmpClient, mibManager, llmClient, logger)

	// Start server
	go func() {
		if err := server.Start(); err != nil {
			logger.Error("Server error", zap.Error(err))
		}
	}()

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	// Graceful shutdown
	logger.Info("Shutting down...")
	if err := server.Shutdown(ctx); err != nil {
		logger.Error("Error during shutdown", zap.Error(err))
	}
}

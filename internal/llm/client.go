package llm

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/akbarkhamidov/snmp-ai/internal/config"
	"github.com/redis/go-redis/v9"
	"go.uber.org/zap"
)

type Query struct {
	Target    string   `json:"target"`
	Operation string   `json:"operation"` // walk, get, bulkwalk
	OIDs      []string `json:"oids"`
}

type Response struct {
	Results []Result `json:"results"`
}

type Result struct {
	OID   string      `json:"oid"`
	Value interface{} `json:"value"`
	Info  string      `json:"info"`
}

type Client struct {
	config *config.LLMConfig
	logger *zap.Logger
	cache  *redis.Client
	mu     sync.RWMutex
}

func NewClient(cfg *config.LLMConfig, redisCfg *config.RedisConfig, logger *zap.Logger) (*Client, error) {
	redisClient := redis.NewClient(&redis.Options{
		Addr: fmt.Sprintf("%s:%d", redisCfg.Host, redisCfg.Port),
		DB:   1, // Use DB 1 for LLM caching
	})

	client := &Client{
		config: cfg,
		logger: logger,
		cache:  redisClient,
	}

	return client, nil
}

func (c *Client) InterpretQuery(query string) (*Query, error) {
	// Check cache first
	cached, err := c.cache.Get(context.Background(), fmt.Sprintf("query:%s", query)).Result()
	if err == nil {
		var q Query
		if err := json.Unmarshal([]byte(cached), &q); err == nil {
			return &q, nil
		}
	}

	// In a real implementation, this would:
	// 1. Call the LLM API to interpret the natural language query
	// 2. Parse the response into a structured Query
	// 3. Cache the result
	// 4. Return the Query

	// For now, return a mock query
	return &Query{
		Target:    "192.168.1.1",
		Operation: "walk",
		OIDs:      []string{"1.3.6.1.2.1"},
	}, nil
}

func (c *Client) ValidateOperation(query *Query) bool {
	// In a real implementation, this would:
	// 1. Validate the target IP/hostname
	// 2. Validate the operation type
	// 3. Validate the OIDs
	// 4. Check permissions/access control

	return true
}

func (c *Client) CacheResponse(query string, result interface{}) error {
	data, err := json.Marshal(result)
	if err != nil {
		return fmt.Errorf("failed to marshal result: %w", err)
	}

	return c.cache.Set(context.Background(), fmt.Sprintf("result:%s", query), data, 0).Err()
}

func (c *Client) GetCachedResponse(query string) (interface{}, error) {
	data, err := c.cache.Get(context.Background(), fmt.Sprintf("result:%s", query)).Result()
	if err != nil {
		return nil, err
	}

	var result interface{}
	if err := json.Unmarshal([]byte(data), &result); err != nil {
		return nil, err
	}

	return result, nil
}

func (c *Client) Close() error {
	return c.cache.Close()
}

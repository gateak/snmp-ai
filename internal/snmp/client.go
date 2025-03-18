package snmp

import (
	"fmt"
	"sync"

	"github.com/akbarkhamidov/snmp-ai/internal/config"
	"github.com/gosnmp/gosnmp"
	"go.uber.org/zap"
)

type Client struct {
	config *config.SNMPConfig
	logger *zap.Logger
	pool   *sync.Pool
}

type SNMPResult struct {
	OID   string
	Type  gosnmp.Asn1BER
	Value interface{}
}

func NewClient(cfg *config.SNMPConfig, logger *zap.Logger) (*Client, error) {
	client := &Client{
		config: cfg,
		logger: logger,
		pool: &sync.Pool{
			New: func() interface{} {
				snmp := &gosnmp.GoSNMP{
					Target:    "", // Will be set per request
					Port:      161,
					Community: cfg.Community,
					Version:   gosnmp.Version2c,
					Timeout:   cfg.Timeout,
					Retries:   cfg.Retries,
				}
				return snmp
			},
		},
	}

	return client, nil
}

func (c *Client) Walk(target string, oid string) ([]SNMPResult, error) {
	snmp := c.pool.Get().(*gosnmp.GoSNMP)
	snmp.Target = target
	defer c.pool.Put(snmp)

	if err := snmp.Connect(); err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", target, err)
	}
	defer snmp.Conn.Close()

	var results []SNMPResult
	err := snmp.Walk(oid, func(pdu gosnmp.SnmpPDU) error {
		results = append(results, SNMPResult{
			OID:   pdu.Name,
			Type:  pdu.Type,
			Value: pdu.Value,
		})
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("walk failed: %w", err)
	}

	return results, nil
}

func (c *Client) Get(target string, oids []string) ([]SNMPResult, error) {
	snmp := c.pool.Get().(*gosnmp.GoSNMP)
	snmp.Target = target
	defer c.pool.Put(snmp)

	if err := snmp.Connect(); err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", target, err)
	}
	defer snmp.Conn.Close()

	result, err := snmp.Get(oids)
	if err != nil {
		return nil, fmt.Errorf("get failed: %w", err)
	}

	var results []SNMPResult
	for _, v := range result.Variables {
		results = append(results, SNMPResult{
			OID:   v.Name,
			Type:  v.Type,
			Value: v.Value,
		})
	}

	return results, nil
}

func (c *Client) BulkWalk(target string, oid string) ([]SNMPResult, error) {
	snmp := c.pool.Get().(*gosnmp.GoSNMP)
	snmp.Target = target
	defer c.pool.Put(snmp)

	if err := snmp.Connect(); err != nil {
		return nil, fmt.Errorf("failed to connect to %s: %w", target, err)
	}
	defer snmp.Conn.Close()

	var results []SNMPResult
	err := snmp.BulkWalk(oid, func(pdu gosnmp.SnmpPDU) error {
		results = append(results, SNMPResult{
			OID:   pdu.Name,
			Type:  pdu.Type,
			Value: pdu.Value,
		})
		return nil
	})

	if err != nil {
		return nil, fmt.Errorf("bulk walk failed: %w", err)
	}

	return results, nil
}

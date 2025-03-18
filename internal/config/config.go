package config

import (
	"os"
	"strconv"

	"github.com/spf13/viper"
)

type Config struct {
	API   APIConfig  `mapstructure:"api"`
	SNMP  SNMPConfig `mapstructure:"snmp"`
	MIB   MIBConfig  `mapstructure:"mib"`
	LLM   LLMConfig  `mapstructure:"llm"`
	Redis RedisConfig `mapstructure:"redis"`
}

type APIConfig struct {
	Port int    `mapstructure:"port"`
	Host string `mapstructure:"host"`
}

type SNMPConfig struct {
	Version   string `mapstructure:"version"`
	Community string `mapstructure:"community"`
	Timeout   int    `mapstructure:"timeout"`
	Retries   int    `mapstructure:"retries"`
}

type MIBConfig struct {
	RepositoryPath string `mapstructure:"repository_path"`
	CacheSize     int    `mapstructure:"cache_size"`
}

type LLMConfig struct {
	APIKey      string  `mapstructure:"api_key"`
	Model       string  `mapstructure:"model"`
	MaxTokens   int     `mapstructure:"max_tokens"`
	Temperature float64 `mapstructure:"temperature"`
}

type RedisConfig struct {
	Host string `mapstructure:"host"`
	Port int    `mapstructure:"port"`
	DB   int    `mapstructure:"db"`
}

func Load() (*Config, error) {
	viper.SetConfigName("config")
	viper.SetConfigType("yaml")
	viper.AddConfigPath("./configs")
	viper.AddConfigPath(".")

	// Set defaults
	viper.SetDefault("api.port", 8080)
	viper.SetDefault("api.host", "0.0.0.0")
	viper.SetDefault("snmp.version", "2c")
	viper.SetDefault("snmp.timeout", 5)
	viper.SetDefault("snmp.retries", 3)
	viper.SetDefault("mib.repository_path", "./configs/mibs")
	viper.SetDefault("mib.cache_size", 1000)
	viper.SetDefault("llm.model", "gpt-4")
	viper.SetDefault("llm.max_tokens", 1000)
	viper.SetDefault("llm.temperature", 0.7)
	viper.SetDefault("redis.host", "localhost")
	viper.SetDefault("redis.port", 6379)
	viper.SetDefault("redis.db", 0)

	// Load configuration from file
	if err := viper.ReadInConfig(); err != nil {
		// If config file is not found, it's ok to continue with defaults and env vars
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, err
		}
	}

	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, err
	}

	// Override with environment variables
	if apiKey := os.Getenv("LLM_API_KEY"); apiKey != "" {
		config.LLM.APIKey = apiKey
	}

	if redisHost := os.Getenv("REDIS_HOST"); redisHost != "" {
		config.Redis.Host = redisHost
	}

	if redisPort := os.Getenv("REDIS_PORT"); redisPort != "" {
		if port, err := strconv.Atoi(redisPort); err == nil {
			config.Redis.Port = port
		}
	}

	return &config, nil
}

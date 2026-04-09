package config

import (
	"fmt"
	"log"
	"os"

	"github.com/BurntSushi/toml"
)

type MainConfig struct {
	Port    int    `toml:"port"`
	AppName string `toml:"appName"`
	Host    string `toml:"host"`
}

type EmailConfig struct {
	Authcode string `toml:"authcode"`
	Email    string `toml:"email" `
}

type RedisConfig struct {
	RedisPort     int    `toml:"port"`
	RedisDb       int    `toml:"db"`
	RedisHost     string `toml:"host"`
	RedisPassword string `toml:"password"`
}

type PostgresConfig struct {
	PostgresPort         int    `toml:"port"`
	PostgresHost         string `toml:"host"`
	PostgresUser         string `toml:"user"`
	PostgresPassword     string `toml:"password"`
	PostgresDatabaseName string `toml:"databaseName"`
	PostgresSSLMode      string `toml:"sslmode"`
}

type JwtConfig struct {
	ExpireDuration int    `toml:"expire_duration"`
	Issuer         string `toml:"issuer"`
	Subject        string `toml:"subject"`
	Key            string `toml:"key"`
}

type OpenAI struct {
	ApiKey    string `toml:"openai_api_key"`
	ModelName string `toml:"openai_model_name"`
	BaseURL   string `toml:"openai_base_url"`
}

type PythonAIConfig struct {
	PythonAIBaseURL        string `toml:"baseURL"`
	PythonAITimeoutSeconds int    `toml:"timeoutSeconds"`
	PythonAIInternalKey    string `toml:"internalKey"`
}

type Config struct {
	EmailConfig    `toml:"emailConfig"`
	RedisConfig    `toml:"redisConfig"`
	PostgresConfig `toml:"postgresConfig"`
	JwtConfig      `toml:"jwtConfig"`
	MainConfig     `toml:"mainConfig"`
	OpenAI         `toml:"openAIConfig"`
	PythonAIConfig `toml:"pythonAIConfig"`
}

type RedisKeyConfig struct {
	CaptchaPrefix string
}

var DefaultRedisKeyConfig = RedisKeyConfig{
	CaptchaPrefix: "captcha:%s",
}

var config *Config

func InitConfig() error {
	config = new(Config)

	var candidates []string
	if explicitPath := os.Getenv("GOPHERAI_CONFIG_FILE"); explicitPath != "" {
		candidates = append(candidates, explicitPath)
	}

	candidates = append(candidates,
		"../../config/gopherai.toml",
		"../config/gopherai.toml",
		"config/config.toml",
	)

	for _, path := range candidates {
		if _, err := os.Stat(path); err != nil {
			continue
		}
		if _, err := toml.DecodeFile(path, config); err != nil {
			return err
		}
		return nil
	}

	err := fmt.Errorf("no config file found, checked: %v", candidates)
	log.Println(err)
	return err
}

func GetConfig() *Config {
	if config == nil {
		config = new(Config)
		_ = InitConfig()
	}
	return config
}

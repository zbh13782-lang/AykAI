package mysql

import (
	"AykAI/config"
	"AykAI/model"
	"fmt"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

var DB *gorm.DB

func InitPostgres() error {
	host := config.GetConfig().PostgresHost
	port := config.GetConfig().PostgresPort
	dbname := config.GetConfig().PostgresDatabaseName
	username := config.GetConfig().PostgresUser
	password := config.GetConfig().PostgresPassword
	sslmode := config.GetConfig().PostgresSSLMode

	if sslmode == "" {
		sslmode = "disable"
	}
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s TimeZone=UTC", host, port, username, password, dbname, sslmode)
	var log logger.Interface
	if gin.Mode() == "debug" {
		log = logger.Default.LogMode(logger.Info)
	} else {
		log = logger.Default
	}
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
		Logger: log,
	})

	if err != nil {
		return err
	}

	sqldb, err := db.DB()
	if err != nil {
		return err
	}
	sqldb.SetMaxIdleConns(10)
	sqldb.SetConnMaxLifetime(time.Hour)
	sqldb.SetMaxOpenConns(100)
	DB = db
	return migration()

}
func migration() error {
	return DB.AutoMigrate(
		new(model.User),
		new(model.Session),
		new(model.Message),
	)
}

func InsertUser(user *model.User) (*model.User, error) {
	err := DB.Create(user).Error
	return user, err
}

func GetUserByUsername(username string) (*model.User, error) {
	user := new(model.User)
	err := DB.Where("username = ? OR email = ?", username, username).First(user).Error
	return user, err
}

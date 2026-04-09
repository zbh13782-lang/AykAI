package main

import (
	"GopherAI/common/mysql"
	"GopherAI/common/redis"
	"GopherAI/config"
	"GopherAI/router"
	"fmt"
	"log"

	"github.com/joho/godotenv"
)

func main() {
	// 先尝试读取当前目录 .env，再回退到项目根目录 .env
	if err := godotenv.Load(".env", "../../.env"); err != nil {
		log.Printf("没有找到可用的 .env 文件: %v", err)
	}

	if err := config.InitConfig(); err != nil {
		log.Fatalf("初始化配置失败: %v", err)
	}

	if err := mysql.InitPostgres(); err != nil {
		log.Fatalf("初始化PostgreSQL失败: %v", err)
	}

	redis.Init()

	r := router.InitRouter()

	conf := config.GetConfig()
	addr := fmt.Sprintf("%s:%d", conf.Host, conf.Port)
	fmt.Printf("服务器正在%s启动...\n", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("启动服务器失败: %v", err)
	}
}

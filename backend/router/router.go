package router

import (
	"GopherAI/middleware/jwt"

	"github.com/gin-gonic/gin"
)

func InitRouter() *gin.Engine {
	r := gin.Default()
	enterRouter := r.Group("/api/v1")
	{
		RegisterUserRouter(enterRouter.Group("/user"))
	}

	{
		AIGroup := enterRouter.Group("/AI")
		AIGroup.Use(jwt.Auth())
		AIRouter(AIGroup)
	}

	return r
}

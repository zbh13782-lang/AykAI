package jwt

import (
	"GopherAI/common/code"
	"GopherAI/controller"
	"GopherAI/utils/myjwt"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)
//JWT中间件
func Auth() gin.HandlerFunc {
	return func(c *gin.Context) {
		res := new(controller.Response)
		var token string
		authHeader := c.GetHeader("Authorization")
		//去掉前缀获得token
		if authHeader != "" && strings.HasPrefix(authHeader, "Bearer ") {
			token = strings.TrimPrefix(authHeader, "Bearer ")
		} else {
			token = c.Query("token") //兼容URL传来的token
		}

		//没有token，不放行，上下文断开
		if token == "" {
			c.JSON(http.StatusOK, res.CodeOf(code.CodeInvalidToken))
			c.Abort()
			return
		}

		log.Println("token is ", token)
		userName, ok := myjwt.ParseToken(token)
		if !ok {
			c.JSON(http.StatusOK, res.CodeOf(code.CodeInvalidToken))
			c.Abort()
			return
		}
		c.Set("userName", userName)
		c.Next()
	}
}

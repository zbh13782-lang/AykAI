package email

import (
	"GopherAI/config"
	"fmt"

	"gopkg.in/gomail.v2"
)

const (
	CodeMsg = "GopherAI验证码(2分钟内有效)："
	UserMsg = "GopherAI账号如下:"
)

func SendCaptcha(email, code, msg string) error {
	m := gomail.NewMessage()

	m.SetHeader("From", config.GetConfig().EmailConfig.Email)
	m.SetHeader("To", email)
	m.SetHeader("Subject", "来自GopherAI的信息")
	m.SetBody("text/plain", msg+" "+code)

	// 使用SSL连接，端口465
	d := gomail.NewDialer("smtp.qq.com", 465, config.GetConfig().EmailConfig.Email, config.GetConfig().Authcode)
	
	// 设置SSL连接
	d.SSL = true
	
	// 发送邮件
	if err := d.DialAndSend(m); err != nil {
		fmt.Printf("DialAndSend err %v:\n", err)
		return err
	}
	fmt.Printf("send mail success\n")
	return nil
}

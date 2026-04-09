package user

import (
	"GopherAI/common/code"
	myemail "GopherAI/common/email"
	myredis "GopherAI/common/redis"
	"GopherAI/dao/user"
	"GopherAI/model"
	"GopherAI/utils"
	"GopherAI/utils/myjwt"
	"log"
)

func Login(username, password string) (string, code.Code) {
	var userInfomation *model.User
	var ok bool

	if ok, userInfomation = user.IsExistUser(username); !ok {
		return "", code.CodeUserNotExist
	}

	if userInfomation.Password != utils.MD5(password) {
		return "", code.CodeInvalidPassword
	}

	token, err := myjwt.GenerateToken(userInfomation.ID, username)

	if err != nil {
		return "", code.CodeServerBusy
	}
	return token, code.CodeSuccess
}

func Register(email, password, captcha string) (string, code.Code) {
	var ok bool
	var userInfomation *model.User

	if ok, _ = user.IsExistUser(email); ok {
		return "", code.CodeUserExist
	}

	if ok, _ = myredis.CheckCaptchaForEmail(email, captcha); !ok {
		return "", code.CodeInvalidCaptcha
	}

	username := utils.GetRandomNumbers(11)

	if userInfomation, ok = user.Register(username, email, password); !ok {
		return "", code.CodeServerBusy
	}

	// 邮件通知失败不应回滚已成功创建的账号，避免“注册失败但账号已存在”的不一致状态。
	if err := myemail.SendCaptcha(email, username, user.UserNameMsg); err != nil {
		log.Printf("register notify email failed for %s: %v", email, err)
	}

	token, err := myjwt.GenerateToken(userInfomation.ID, userInfomation.Username)

	if err != nil {
		return "", code.CodeServerBusy
	}
	return token, code.CodeSuccess
}

// 往指定邮箱发送验证码
// 分为以下任务：
// 1：先存放redis
// 2：再进行远程发送
func SendCaptcha(email_ string) code.Code {
	send_code := utils.GetRandomNumbers(6)
	if err := myredis.SetCaptchForEmail(email_, send_code); err != nil {
		return code.CodeServerBusy
	}

	if err := myemail.SendCaptcha(email_, send_code, myemail.CodeMsg); err != nil {
		return code.CodeServerBusy
	}
	return code.CodeSuccess
}

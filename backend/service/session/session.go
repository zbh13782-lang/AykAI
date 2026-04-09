package session

import (
	"log"
	"net/http"

	"AykAI/common/code"
	messageDao "AykAI/dao/message"
	sessionDao "AykAI/dao/session"
	"AykAI/model"

	"github.com/google/uuid"
)

func persistMessage(sessionID, userName, content string, isUser bool) {
	if content == "" {
		return
	}
	_, err := messageDao.CreateMessage(&model.Message{
		SessionID: sessionID,
		UserName:  userName,
		Content:   content,
		IsUser:    isUser,
	})
	if err != nil {
		log.Printf("persist message failed: session=%s user=%s err=%v", sessionID, userName, err)
	}
}

func verifySessionOwner(userName, sessionID string) bool {
	s, err := sessionDao.GetSessionByID(sessionID)
	if err != nil {
		return false
	}
	return s.UserName == userName
}

// 获取用户的所有SessionInfo
func GetUserSessionsByUserName(userName string) ([]model.SessionInfo, error) {
	sessions, err := sessionDao.GetSessionsByUserName(userName)
	if err != nil {
		return nil, err
	}
	infos := make([]model.SessionInfo, 0, len(sessions))
	for _, s := range sessions {
		infos = append(infos, model.SessionInfo{
			SessionID: s.ID,
			Title:     s.Title,
		})
	}
	return infos, nil
}

// 创建新会话(同步生成)
func CreateSessionAndSendMessage(userName, userQuestion, modelType string) (string, string, code.Code) {
	_ = modelType
	newSession := &model.Session{
		ID:       uuid.New().String(),
		UserName: userName,
		Title:    userQuestion,
	}

	createdSession, err := sessionDao.CreateSession(newSession)
	if err != nil {
		log.Println("CreateSessionAndSendMessage CreateSession error:", err)
		return "", "", code.CodeServerBusy
	}

	persistMessage(createdSession.ID, userName, userQuestion, true)

	client := newPythonAIClient()
	answer, err := client.Query(userName, createdSession.ID, userQuestion)
	if err != nil {
		log.Println("CreateSessionAndSendMessage python query error:", err)
		return "", "", code.AIModelFail
	}

	persistMessage(createdSession.ID, userName, answer, false)
	return createdSession.ID, answer, code.CodeSuccess
}

func CreateStreamSessionOnly(userName string, userQuestion string) (string, code.Code) {
	newSession := &model.Session{
		ID:       uuid.New().String(),
		UserName: userName,
		Title:    userQuestion,
	}

	createdSession, err := sessionDao.CreateSession(newSession)
	if err != nil {
		log.Println("CreateStreamSessionOnly CreateSession error:", err)
		return "", code.CodeServerBusy
	}

	return createdSession.ID, code.CodeSuccess
}

func StreamMessageToExistingSession(userName, sessionID, userQuestion, modelType string, writer http.ResponseWriter) code.Code {
	_ = modelType
	flusher, ok := writer.(http.Flusher)
	if !ok {
		log.Println("StreamMessageToExistingSession: Streaming unsupported")
		return code.CodeServerBusy
	}
	if !verifySessionOwner(userName, sessionID) {
		return code.CodeForbidden
	}

	persistMessage(sessionID, userName, userQuestion, true)

	client := newPythonAIClient()
	cb := func(msg string) {
		_, err := writer.Write([]byte("data: " + msg + "\n\n"))
		if err != nil {
			log.Println("[SSE] write error:", err)
			return
		}
		flusher.Flush()
	}
	answer, err := client.StreamQuery(userName, sessionID, userQuestion, cb)
	if err != nil {
		log.Println("StreamMessageToExistingSession python stream error:", err)
		return code.AIModelFail
	}

	if answer != "" {
		persistMessage(sessionID, userName, answer, false)
	}

	_, err = writer.Write([]byte("data: [DONE]\n\n"))
	if err != nil {
		log.Println("StreamMessageToExistingSession write DONE error:", err)
		return code.AIModelFail
	}
	flusher.Flush()
	return code.CodeSuccess
}

// 整合上面两个函数
func CreateStreamSessionAndSendMessage(userName, userQuestion, modelType string, writer http.ResponseWriter) (string, code.Code) {
	sessionID, code_ := CreateStreamSessionOnly(userName, userQuestion)
	if code_ != code.CodeSuccess {
		return "", code_
	}

	code_ = StreamMessageToExistingSession(userName, sessionID, userQuestion, modelType, writer)
	if code_ != code.CodeSuccess {
		return sessionID, code_
	}

	return sessionID, code.CodeSuccess
}

func ChatSend(userName, sessionID, userQuestion, modelType string) (string, code.Code) {
	_ = modelType
	if !verifySessionOwner(userName, sessionID) {
		return "", code.CodeForbidden
	}

	persistMessage(sessionID, userName, userQuestion, true)

	client := newPythonAIClient()
	answer, err := client.Query(userName, sessionID, userQuestion)
	if err != nil {
		log.Println("ChatSend python query error:", err)
		return "", code.AIModelFail
	}

	persistMessage(sessionID, userName, answer, false)
	return answer, code.CodeSuccess
}

func GetChatHistory(userName, sessionID string) ([]model.History, code.Code) {
	if !verifySessionOwner(userName, sessionID) {
		return nil, code.CodeForbidden
	}

	messages, err := messageDao.GetMessagesBySessionID(sessionID)
	if err != nil {
		return nil, code.CodeServerBusy
	}
	if len(messages) == 0 {
		return []model.History{}, code.CodeSuccess
	}

	history := make([]model.History, 0, len(messages))
	for _, msg := range messages {
		history = append(history, model.History{
			IsUser:  msg.IsUser,
			Content: msg.Content,
		})
	}
	return history, code.CodeSuccess
}

func ChatStreamSend(userName, sessionID, userQuestion, modelType string, writer http.ResponseWriter) code.Code {
	return StreamMessageToExistingSession(userName, sessionID, userQuestion, modelType, writer)
}

func IngestMarkdown(userName, sessionID, docID, source, content string, metadata map[string]any) (int, int, code.Code) {
	if source == "" {
		source = "go-gateway"
	}
	client := newPythonAIClient()
	parents, children, err := client.Ingest(userName, sessionID, docID, source, content, metadata)
	if err != nil {
		log.Println("IngestMarkdown python ingest error:", err)
		return 0, 0, code.AIModelFail
	}
	return parents, children, code.CodeSuccess
}

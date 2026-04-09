package session

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"AykAI/config"
)

type pythonAIClient struct {
	baseURL     string
	internalKey string
	httpClient  *http.Client
}

type queryResp struct {
	Status string `json:"status"`
	Answer string `json:"answer"`
}

type ingestResp struct {
	Status           string `json:"status"`
	InsertedParents  int    `json:"inserted_parents"`
	InsertedChildren int    `json:"inserted_children"`
}

type sseEnvelope struct {
	Event string          `json:"event"`
	Data  json.RawMessage `json:"data"`
}

func newPythonAIClient() *pythonAIClient {
	cfg := config.GetConfig()
	timeout := time.Duration(cfg.PythonAITimeoutSeconds) * time.Second
	if timeout <= 0 {
		timeout = 120 * time.Second
	}
	baseURL := strings.TrimRight(cfg.PythonAIBaseURL, "/")
	return &pythonAIClient{
		baseURL:     baseURL,
		internalKey: cfg.PythonAIInternalKey,
		httpClient: &http.Client{
			Timeout: timeout,
		},
	}
}

func (c *pythonAIClient) buildRequest(method, path string, payload any, userName, sessionID string) (*http.Request, error) {
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequest(method, c.baseURL+path, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.internalKey != "" {
		req.Header.Set("X-Internal-Key", c.internalKey)
	}
	if userName != "" {
		req.Header.Set("X-User-Name", userName)
	}
	if sessionID != "" {
		req.Header.Set("X-Session-Id", sessionID)
	}
	return req, nil
}

func (c *pythonAIClient) Query(userName, sessionID, question string) (string, error) {
	req, err := c.buildRequest(http.MethodPost, "/api/query", map[string]any{
		"query":  question,
		"stream": false,
	}, userName, sessionID)
	if err != nil {
		return "", err
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("python query failed: status=%d body=%s", resp.StatusCode, string(body))
	}

	var out queryResp
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	if out.Status != "ok" {
		return "", fmt.Errorf("python query returned non-ok status: %s", out.Status)
	}
	return out.Answer, nil
}

func (c *pythonAIClient) StreamQuery(userName, sessionID, question string, onData func(string)) (string, error) {
	req, err := c.buildRequest(http.MethodPost, "/api/query/stream", map[string]any{
		"query":  question,
		"stream": true,
	}, userName, sessionID)
	if err != nil {
		return "", err
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("python query stream failed: status=%d body=%s", resp.StatusCode, string(body))
	}

	reader := bufio.NewReader(resp.Body)
	var answerBuilder strings.Builder
	for {
		line, readErr := reader.ReadString('\n')
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			return "", readErr
		}

		trimmed := strings.TrimSpace(line)
		if !strings.HasPrefix(trimmed, "data:") {
			continue
		}
		payload := strings.TrimSpace(strings.TrimPrefix(trimmed, "data:"))
		if payload == "" {
			continue
		}

		onData(payload)

		var envelope sseEnvelope
		if err := json.Unmarshal([]byte(payload), &envelope); err != nil {
			continue
		}
		switch envelope.Event {
		case "token":
			var token string
			if err := json.Unmarshal(envelope.Data, &token); err == nil {
				answerBuilder.WriteString(token)
			}
		case "done":
			var doneData struct {
				Answer string `json:"answer"`
			}
			if err := json.Unmarshal(envelope.Data, &doneData); err == nil && doneData.Answer != "" {
				answerBuilder.Reset()
				answerBuilder.WriteString(doneData.Answer)
			}
		}
	}

	return answerBuilder.String(), nil
}

func (c *pythonAIClient) Ingest(userName, sessionID, docID, source, content string, metadata map[string]any) (int, int, error) {
	if metadata == nil {
		metadata = map[string]any{}
	}
	req, err := c.buildRequest(http.MethodPost, "/api/ingest", map[string]any{
		"doc_id":   docID,
		"source":   source,
		"content":  content,
		"metadata": metadata,
	}, userName, sessionID)
	if err != nil {
		return 0, 0, err
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return 0, 0, fmt.Errorf("python ingest failed: status=%d body=%s", resp.StatusCode, string(body))
	}

	var out ingestResp
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return 0, 0, err
	}
	if out.Status != "ok" {
		return 0, 0, fmt.Errorf("python ingest returned non-ok status: %s", out.Status)
	}
	return out.InsertedParents, out.InsertedChildren, nil
}

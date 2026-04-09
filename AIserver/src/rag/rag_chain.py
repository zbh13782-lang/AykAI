from __future__ import annotations

from collections.abc import Iterator

from langchain_core.prompts import ChatPromptTemplate
'''
提示词可单独写。
英文提问效果更佳~~~
'''
RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
             "You are a helpful assistant. Answer based only on provided context. If unsure, say you do not know.",
        ),
        (
            "human",
            "Question:\n{question}\n\nContext:\n{context}\n\nAnswer in Chinese with concise citations like [source]."
        )
    ]
)

def generate_answer(chat_model,question:str,context_blocks:list[dict]) -> str:
    # 将检索到的上下文拼接为可引用格式，便于模型在回答中给出来源标注。
    context_text = "\n\n".join([f"[{b['source']}] {b['content']}" for b in context_blocks])
    prompt = RAG_PROMPT.format_messages(question=question, context=context_text)
    return chat_model.invoke(prompt).content

def stream_answer(chat_model, question: str, context_blocks: list[dict]) -> Iterator[str]:
    # 流式生成时逐块透传 token，供 SSE 接口实时返回给前端。
    context_text = "\n\n".join([f"[{b['source']}] {b['content']}" for b in context_blocks])
    prompt = RAG_PROMPT.format_messages(question=question, context=context_text)
    for chunk in chat_model.stream(prompt):
        text = getattr(chunk, "content", "")
        if text:
            yield text

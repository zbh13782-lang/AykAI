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
             "你是AykAI，请根据提供的信息回答问题，如果是简单的问题比如你是谁这种不需要参考的问题就直接回答，如果你不确定问题的答案，就回答“抱歉，我不清楚问题的答案”",
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

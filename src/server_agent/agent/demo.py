from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="Baichuan-M3",
    api_key="sk-d6c2cde84b8bf50a4ef1b614d19ec13a",
    base_url="https://api.baichuan-ai.com/v1",
    streaming=True,
)

for chunk in model.stream("你可以解读CT吗"):
    print(chunk.content, end="", flush=True)

from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    project="digital-human-478009",
    location="us-central1",
)

print(llm.invoke("hi"))
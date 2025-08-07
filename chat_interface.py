import openai
import streamlit as st
import os
from dotenv import load_dotenv
from langchain_community.retrievers import AzureAISearchRetriever
from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough

load_dotenv()

# OpenAI 설정
openai.api_key = os.getenv('OPENAI_API_KEY')
openai.azure_endpoint = os.getenv('AZURE_ENDPOINT')
openai.api_type = os.getenv('OPENAI_API_TYPE')
openai.api_version = os.getenv('OPENAI_API_VERSION')
DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_LLM')

# PostgreSQL 연결 설정
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': os.getenv('DB_PORT'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD')
}

def get_openai_client(messages):
    try:
        response = openai.chat.completions.create(
            model = DEPLOYMENT_NAME,
            messages=messages,
            temperature=0.4
        )
        return response.choices[0].message.content
    
    except Exception as e:
        return None
    
# Streamlit UI 설정
st.title("KT Genius")
st.write("무엇을 도와드릴까요?")

# 채팅 메시지의 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": "당신은 학습 도우미 입니다. 학습자의 학습 정보를 바탕으로 다음 학습을 추천해줄 수 있습니다."}
    ]

# 채팅 메시지 표시
for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])

# 사용자 입력 받기
if prompt := st.chat_input("질문을 입력하세요."):
    st.session_state.messages.append({"role":"user","content":prompt})
    st.chat_message("user").write(prompt)

    # openAI에 메시지 전송 및 응답 받기
    response = get_openai_client(st.session_state.messages)
    st.session_state.messages.append({"role":"assistant","content":response})
    st.chat_message("assistant").write(response)
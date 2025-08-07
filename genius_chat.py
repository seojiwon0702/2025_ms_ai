import openai
import streamlit as st
import os
import psycopg2
import requests
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

class DatabaseManager:
    """데이터베이스 연결 및 쿼리 관리"""
    
    def __init__(self, config):
        self.config = config
    
    def get_connection(self):
        """데이터베이스 연결"""
        try:
            conn = psycopg2.connect(**self.config)
            return conn
        except Exception as e:
            st.error(f"오류가 발생하였습니다. 관리자에게 문의해주세요.")
            return None
    
    def get_user_learning_history(self, user_id):
        """학습자의 학습 이력 조회"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT 
                    c.cont_id,
                    c.cont_title,
                    c.cont_desc,
                    c.cont_lvl,
                    c.cont_ctg_cd,
                    cu.educ_sts_cd
                FROM tb_cont c
                JOIN tb_cont_user cu ON c.cont_id = cu.cont_id
                WHERE cu.user_id = %s
                ORDER BY cu.educ_sts_cd DESC, c.cont_lvl
            """
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            
            learning_history = []
            for row in results:
                learning_history.append({
                    'cont_id': row[0],
                    'cont_title': row[1],
                    'cont_desc': row[2],
                    'cont_lvl': row[3],
                    'cont_ctg_cd': row[4],
                    'educ_sts_cd': row[5]
                })
            
            cursor.close()
            conn.close()
            return learning_history
            
        except Exception as e:
            st.error(f"학습 이력 조회에 실패하였습니다. 다시 시도해주세요.")
            conn.close()
            return None
    
    def get_recommended_courses(self, category, level):
        """추천 과정 조회"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            params = [category, level]
            
            query = f"""
                SELECT cont_id, cont_title, cont_desc,cont_lvl, cont_ctg_cd
                FROM tb_cont
                WHERE cont_ctg_cd = %s AND cont_lvl = %s
                LIMIT 3
            """
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            courses = []
            for row in results:
                courses.append({
                    'cont_id': row[0],
                    'cont_title': row[1],
                    'cont_desc': row[2],
                    'cont_lvl': row[3],
                    'cont_ctg_cd': row[4]
                })
            
            cursor.close()
            conn.close()
            return courses
            
        except Exception as e:
            st.error(f"죄송합니다. 추천 과정 조회 실패하였습니다. 다시 질문해주세요.{e}")
            conn.close()
            return None
    
    def get_other_categories(self, exclude_category):
        """다른 카테고리 조회"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT cont_ctg_cd
                FROM tb_cont
                WHERE cont_ctg_cd != %s
                LIMIT 3
            """
            cursor.execute(query, (exclude_category,))
            results = cursor.fetchall()
            
            categories = [row[0] for row in results]
            cursor.close()
            conn.close()
            return categories
            
        except Exception as e:
            st.error(f"카테고리 조회에 실패하였습니다. 다시 시도해주세요.")
            conn.close()
            return None
        
    def get_user_info(self, user_id):
        """사용자 정보 조회"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            query = """
                SELECT user_id, user_nm
                FROM tb_user
                WHERE user_id = %s
            """
            cursor.execute(query, (user_id,))
            results = cursor.fetchall()
            
            user_info = []
            
            user_info.append({
                'user_id': results[0][0],
                'user_nm': results[0][1]   
            })
            cursor.close()
            conn.close()
            return user_info
            
        except Exception as e:
            st.error(f"사용자 조회에 실패하였습니다. 사번 확인 후 다시 시도해주세요.")
            conn.close()
            return None

class LearningRecommendationSystem:
    """학습 추천 시스템"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    def get_user_info(self, user_id):
        """사용자 정보 조회"""
        user_info = self.db_manager.get_user_info(user_id)
        if not user_info:
            return "사용자 정보를 찾을 수 없습니다. 사번을 확인해주세요."
        return f"{user_info[0]['user_nm']}님 안녕하세요!"
    
    def analyze_learning_level(self, learning_history):
        """학습자의 현재 수준 분석"""
        if not learning_history:
            return None, None, [], []
        
        # 학습 상태별로 분류
        completed_courses = [course for course in learning_history if course['educ_sts_cd'] == '9']
        in_progress_courses = [course for course in learning_history if course['educ_sts_cd'] == '1']
        
        # 학습중인 과정이 있는 경우 우선 처리
        if in_progress_courses:
            # 학습중인 과정의 카테고리와 레벨 정보
            current_course = in_progress_courses[0]  # 가장 최근 학습중인 과정
            return (
                current_course['cont_lvl'], 
                current_course['cont_ctg_cd'], 
                [course['cont_id'] for course in learning_history],  # 모든 과정 제외
                in_progress_courses
            )
        
        # 완료된 과정만 있는 경우
        if not completed_courses:
            return 'L', learning_history[0]['cont_ctg_cd'] if learning_history else None, [], []
        
        # 카테고리별 최고 레벨 확인
        category_levels = {}
        for course in completed_courses:
            category = course['cont_ctg_cd']
            level = course['cont_lvl']
            
            if category not in category_levels:
                category_levels[category] = level
            else:
                # L < M < H 순서로 비교
                current_level = category_levels[category]
                if self._compare_levels(level, current_level) > 0:
                    category_levels[category] = level
        
        # 가장 최근 학습한 카테고리와 레벨
        recent_category = completed_courses[0]['cont_ctg_cd']
        recent_level = category_levels.get(recent_category, 'L')
        
        return recent_level, recent_category, [course['cont_id'] for course in completed_courses], []
    
    def _compare_levels(self, level1, level2):
        """레벨 비교 (L=0, M=1, H=2)"""
        level_map = {'L': 0, 'M': 1, 'H': 2}
        return level_map.get(level1, 0) - level_map.get(level2, 0)
    
    def get_next_level(self, current_level, is_difficult=False):
        """다음 레벨 결정"""
        if is_difficult:
            if current_level == 'M':
                return 'L'
            elif current_level == 'H':
                return 'M'
            else:
                return 'L'
        else:
            if current_level == 'L':
                return 'M'
            elif current_level == 'M':
                return 'H'
            else:
                return 'H'
    
    def recommend_courses(self, user_id, is_difficult=False):
        """과정 추천"""
        # 학습 이력 조회
        learning_history = self.db_manager.get_user_learning_history(user_id)
        
        if not learning_history:
            return "학습 이력을 찾을 수 없습니다. 먼저 기초 과정부터 시작해보세요."
        
        # 현재 수준 분석
        current_level, current_category, exclude_course_ids, in_progress_courses = self.analyze_learning_level(learning_history)
        
        # 학습중인 과정이 있는 경우
        if in_progress_courses:
            current_course = in_progress_courses[0]
            
            if is_difficult:
                # 어렵다고 하면 같은 카테고리의 더 쉬운 레벨 추천
                easier_level = self.get_next_level(current_course['cont_lvl'], is_difficult=True)
                recommended_courses = self.db_manager.get_recommended_courses(
                    current_category, 
                    easier_level, 
                    exclude_course_ids
                )
                
                if recommended_courses:
                    return self.format_recommendation_response(
                        recommended_courses,
                        f"현재 학습중인 '{current_course['cont_title']}'이 어려우시다면, 더 쉬운 과정부터 시작해보세요:"
                    )
            else:
                # 학습중인 과정이 있으면 같은 카테고리의 다른 과정 추천
                recommended_courses = self.db_manager.get_recommended_courses(
                    current_category, 
                    current_course['cont_lvl']
                )
                
                if recommended_courses:
                    return self.format_recommendation_response(
                        recommended_courses,
                        f"현재 '{current_course['cont_title']}'을 학습중이시네요. 같은 수준의 다른 과정도 추천드립니다:"
                    )
                
                # 같은 레벨에 다른 과정이 없으면 다른 카테고리 추천
                other_categories = self.db_manager.get_other_categories(current_category)
                if other_categories:
                    recommended_courses = []
                    for category in other_categories[:2]:  # 최대 2개 카테고리
                        courses = self.db_manager.get_recommended_courses(category, current_course['cont_lvl'])
                        if courses:
                            recommended_courses.extend(courses[:2])  # 카테고리당 최대 2개
                    
                    if recommended_courses:
                        return self.format_recommendation_response(
                            recommended_courses,
                            f"현재 학습중인 과정과 병행할 수 있는 다른 분야의 과정을 추천드립니다:"
                        )
            
            return f"현재 '{current_course['cont_title']}'을 학습중입니다. 해당 과정을 완료한 후 다시 추천을 요청해주세요."
        
        # 완료된 과정만 있는 경우 (기존 로직)
        if current_level == 'H' and not is_difficult:
            # H 레벨 완료자는 다른 카테고리 추천
            other_categories = self.db_manager.get_other_categories(current_category)
            if other_categories:
                recommended_courses = []
                for category in other_categories:
                    courses = self.db_manager.get_recommended_courses(category, 'L')
                    if courses:
                        recommended_courses.extend(courses[:1])  # 카테고리당 1개씩
                
                if recommended_courses:
                    return self.format_recommendation_response(
                        recommended_courses, 
                        f"{current_category} 카테고리의 고급 과정을 완료하셨네요! 새로운 영역에 도전해보세요:"
                    )
        
        # 다음 레벨 결정
        next_level = self.get_next_level(current_level, is_difficult)
        
        # 추천 과정 조회
        recommended_courses = self.db_manager.get_recommended_courses(
            current_category, 
            next_level, 
            exclude_course_ids
        )
        
        if not recommended_courses:
            return f"추천할 수 있는 {next_level} 레벨 과정이 없습니다."
        
        difficulty_msg = "더 쉬운" if is_difficult else "다음 단계"
        return self.format_recommendation_response(
            recommended_courses,
            f"현재 수준에서 {difficulty_msg} 과정을 추천드립니다:"
        )
    
    def format_recommendation_response(self, courses, intro_message):
        """추천 응답 포맷"""
        if not courses:
            return "추천할 수 있는 과정이 없습니다."
            
        response = f"{intro_message}\n\n"
        
        for i, course in enumerate(courses, 1):
            level_name = {'L': '초급', 'M': '중급', 'H': '고급'}.get(course['cont_lvl'], course['cont_lvl'])
            response += f"{i}. **{course['cont_title']}** ({level_name})\n"
            response += f"   - 카테고리: {course['cont_ctg_cd']}\n"
            response += f"   - 과정 설명: {course['cont_desc']}\n\n"
        
        return response

def get_openai_client(messages):
    """OpenAI 클라이언트 호출"""
    try:
        response = openai.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=messages,
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"OpenAI 응답 생성 중 오류가 발생했습니다. 다시 시도해주세요."

def is_learning_recommendation_request(message):
    """학습 추천 요청인지 판단"""
    learning_keywords = [
        '학습 추천', '과정 추천', '다음 학습', '추천해줘', '추천해주세요',
        '무엇을 공부', '다음에 뭘', '어떤 과정', '학습 계획', '커리큘럼',
        '어려워', '쉬운 과정', '기초부터', '다시 배우고'
    ]
    
    return any(keyword in message.lower() for keyword in learning_keywords)

def is_difficult_request(message):
    """어려움을 호소하는 요청인지 판단"""
    difficult_keywords = ['어려워', '어렵다', '힘들어', '이해가 안', '쉬운', '기초', '다시']
    return any(keyword in message.lower() for keyword in difficult_keywords)

# Streamlit UI 설정
st.title("🎓 KT Genius - 학습 도우미")
st.write("개인화된 학습 추천과 궁금한 것들을 물어보세요!")

# 데이터베이스 매니저 및 추천 시스템 초기화
db_manager = DatabaseManager(DB_CONFIG)
recommendation_system = LearningRecommendationSystem(db_manager)

# 사이드바에서 사용자 ID 입력
with st.sidebar:
    st.header("👤 사용자 정보")
    user_id = st.text_input("사번을 입력하세요:", value="", help="학습 추천을 받으려면 사번이 필요합니다.")
    
    if user_id:
        st.success(recommendation_system.get_user_info(user_id))
    else:
        st.warning("사번을 입력해주세요.")

# 채팅 메시지의 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": """당신은 KT Genius의 학습 도우미입니다. 
        학습자가 학습 추천을 요청하면 개인화된 추천을 제공하고, 
        다른 질문에는 웹에서 검색한 최신 정보로 답변해주세요.
        다만 학습과 무관한 질문에는 "죄송합니다. 이해하지 못했습니다."라고 답변해주세요.
        친근하고 도움이 되는 톤으로 대화해주세요."""}
    ]

# 채팅 메시지 표시
for message in st.session_state.messages:
    if message["role"] != "system":  # 시스템 메시지는 표시하지 않음
        with st.chat_message(message["role"]):
            st.write(message["content"])

# 사용자 입력 받기
if prompt := st.chat_input("질문을 입력하세요..."):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    # 응답 생성
    with st.chat_message("assistant"):
        with st.spinner("답변을 생성하고 있습니다..."):
            
            # 학습 추천 요청인지 확인
            if is_learning_recommendation_request(prompt):
                if not user_id:
                    response = "학습 추천을 받으려면 사번을 입력해주세요."
                else:
                    # 어려움을 호소하는지 확인
                    is_difficult = is_difficult_request(prompt)
                    response = recommendation_system.recommend_courses(user_id, is_difficult)
            
            else:
                # 일반적인 질문은 OpenAI로 처리 (웹 검색 결과 포함)
                # 웹 검색을 위한 프롬프트 추가
                enhanced_messages = st.session_state.messages.copy()
                enhanced_messages.append({
                    "role": "system", 
                    "content": f"사용자의 질문 '{prompt}'에 대해 최신 정보를 포함하여 답변해주세요. 학습과 관련이 없는 질문인 경우 죄송합니다. 이해하지 못했습니다. 라는 답변을 해주세요."
                })
                
                response = get_openai_client(enhanced_messages)
            
            st.write(response)
    
    # 어시스턴트 응답 저장
    st.session_state.messages.append({"role": "assistant", "content": response})

# 하단에 사용법 안내
with st.expander("💡 사용법 안내"):
    st.markdown("""
    **학습 추천 받기:**
    - "학습 추천해주세요", "다음에 무엇을 공부할까요?" 등으로 질문
    - 어려운 경우: "현재 과정이 어려워요", "쉬운 과정 추천해주세요"
    
    **일반 질문:**
    - IT 기술, 업무 관련 질문 등 자유롭게 물어보세요
    - 최신 정보가 포함된 답변을 제공합니다
    
    **주의사항:**
    - 학습 추천을 받으려면 반드시 사번을 입력해주세요
    - 오류 발생 시 관리자에게 문의해주세요
    """)
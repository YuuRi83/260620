# dog.ceo API 예시
import streamlit as st
import requests

st.title("🐶 랜덤 강아지 사진 뽑기")

if st.button("강아지 데려오기!"):
    # 1. API 요청
    response = requests.get("https://dog.ceo/api/breeds/image/random")
    data = response.json()
    
    # 2. 이미지 URL 추출 및 출력
    image_url = data["message"]
    st.image(image_url, width=400)

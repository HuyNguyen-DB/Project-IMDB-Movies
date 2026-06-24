# chatbot/app.py

import os
import re
import shutil

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient
import torch

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    pipeline,
    BitsAndBytesConfig,
)

from langchain.llms import HuggingFacePipeline
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_core.documents import Document


# =========================================================
# 1. LOAD ENV
# =========================================================

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "Movie")
MONGO_MOVIE_COLLECTION = os.getenv(
    "MONGO_MOVIE_COLLECTION",
    "recommendations_movie"
)
MONGO_ROOM_COLLECTION = os.getenv(
    "MONGO_ROOM_COLLECTION",
    "recommendations_screenroom"
)

REBUILD_CHROMA = os.getenv("REBUILD_CHROMA", "false").lower() == "true"

BASE_DIR = os.path.dirname(__file__)
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")


if not MONGO_URI:
    raise ValueError("Thiếu MONGO_URI trong file chatbot/.env")


# =========================================================
# 2. LOAD MODEL QWEN
# =========================================================

model_id = "Qwen/Qwen2.5-3B-Instruct"

quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True,
)

tokenizer = AutoTokenizer.from_pretrained(model_id)

model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="auto",
    quantization_config=quantization_config,
)

pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=64,
    temperature=0.0,
    top_p=0.9,
    repetition_penalty=1.2,
    do_sample=False,
    return_full_text=False,
    pad_token_id=tokenizer.eos_token_id,
)

llm = HuggingFacePipeline(pipeline=pipe)


# =========================================================
# 3. LOAD DATA FROM MONGODB
# =========================================================

def load_data_from_mongodb():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]

    movies = list(
    db[MONGO_MOVIE_COLLECTION]
    .find(
        {
            "averageRating": {"$ne": None},
            "numVotes": {"$ne": None},
        },
        {"_id": 0}
    )
    .sort("numVotes", -1)
    .limit(100000)
)

    rooms = list(
        db[MONGO_ROOM_COLLECTION].find(
            {},
            {"_id": 0}
        )
    )

    print(f"Số phim từ MongoDB: {len(movies)}")
    print(f"Số phòng từ MongoDB: {len(rooms)}")

    return movies, rooms


movies, rooms = load_data_from_mongodb()


# =========================================================
# 4. HELPER
# =========================================================

def safe_meta(value, default=""):
    if value is None:
        return default

    if isinstance(value, list):
        cleaned = [
            str(v)
            for v in value
            if v is not None
        ]

        if not cleaned:
            return default

        return ", ".join(cleaned)

    if isinstance(value, dict):
        return str(value)

    if str(value).strip() == "":
        return default

    return value


def to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# =========================================================
# 5. CONVERT MONGODB DATA -> DOCUMENTS
# =========================================================

def build_documents(movies, rooms):
    docs = []

    # ===== MOVIES =====
    for m in movies:
        tconst = str(safe_meta(m.get("tconst"))).strip()
        title = str(safe_meta(m.get("primaryTitle"), "Không rõ tên")).strip()
        year = str(safe_meta(m.get("startYear"), "Không rõ năm")).strip()
        genres = str(safe_meta(m.get("genres"), "Không rõ thể loại")).strip()
        rating = str(safe_meta(m.get("averageRating"), "Chưa có điểm")).strip()
        runtime = str(safe_meta(m.get("runtimeMinutes"), "Không rõ")).strip()

        if not tconst or title == "Không rõ tên":
            continue

        content = f"""
[PHIM]
ID: {tconst}
Tên: {title}
Năm: {year}
Thể loại: {genres}
Điểm: {rating}
Thời lượng: {runtime} phút
Link đặt phim: /select-movie/{tconst}/
"""

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "type": "movie",
                    "tconst": tconst,
                    "title": title,
                    "genres": genres.lower(),
                    "year": year,
                    "rating": rating,
                    "runtime": runtime,
                    "url": f"/select-movie/{tconst}/",
                },
            )
        )

    # ===== ROOMS =====
    for r in rooms:
        room_id = str(safe_meta(r.get("room_id"))).strip()
        name = str(safe_meta(r.get("name"), "Không rõ phòng")).strip()
        status = str(safe_meta(r.get("status"), "unknown")).strip()
        price = str(safe_meta(r.get("price_per_30min"), "0")).strip()
        description = str(safe_meta(r.get("description"), "")).strip()

        if not room_id or name == "Không rõ phòng":
            continue

        # Nếu chỉ muốn chatbot gợi ý phòng còn trống thì mở đoạn này:
        # if status != "available":
        #     continue

        content = f"""
[PHÒNG]
ID: {room_id}
Tên: {name}
Mô tả: {description}
Trạng thái: {status}
Giá mỗi 30 phút: {price}
Link phòng: /room/{room_id}/
"""

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "type": "room",
                    "room_id": room_id,
                    "name": name,
                    "status": status,
                    "price_per_30min": price,
                    "url": f"/room/{room_id}/",
                },
            )
        )

    print(f"Tổng documents: {len(docs)}")

    return docs


docs = build_documents(movies, rooms)


# =========================================================
# 6. EMBEDDING + CHROMA LOCAL
# =========================================================

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

if REBUILD_CHROMA and os.path.exists(CHROMA_DIR):
    print("Xóa Chroma DB cũ...")
    shutil.rmtree(CHROMA_DIR)

db_exists = os.path.exists(CHROMA_DIR) and len(os.listdir(CHROMA_DIR)) > 0

if db_exists:
    print("Load vector DB local cũ...")
    vectordb = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )
else:
    print("Tạo vector DB local mới...")

    vectordb = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )

    batch_size = 2000

    for i in range(0, len(docs), batch_size):
        batch = docs[i:i + batch_size]
        print(f"Đang xử lý batch {i} -> {i + len(batch)}")
        vectordb.add_documents(batch)

    vectordb.persist()


# =========================================================
# 7. QUERY PARSER
# =========================================================

genre_map = {
    "hành động": "action",
    "phiêu lưu": "adventure",
    "hoạt hình": "animation",
    "tiểu sử": "biography",
    "hài": "comedy",
    "tội phạm": "crime",
    "tài liệu": "documentary",
    "chính kịch": "drama",
    "drama": "drama",
    "gia đình": "family",
    "kỳ ảo": "fantasy",
    "phim noir": "film-noir",
    "game show": "game-show",
    "lịch sử": "history",
    "kinh dị": "horror",
    "âm nhạc": "music",
    "nhạc kịch": "musical",
    "bí ẩn": "mystery",
    "tin tức": "news",
    "truyền hình thực tế": "reality-tv",
    "tình cảm": "romance",
    "lãng mạn": "romance",
    "khoa học viễn tưởng": "sci-fi",
    "viễn tưởng": "sci-fi",
    "thể thao": "sport",
    "talk show": "talk-show",
    "giật gân": "thriller",
    "chiến tranh": "war",
    "cao bồi miền tây": "western",
}


def parse_query(query):
    q = query.lower()

    intent = "movie"

    if re.search(r"\d+\s*người", q):
        intent = "both"

    if "phòng" in q:
        intent = "room"

    people = None
    match = re.search(r"(\d+)\s*người", q)

    if match:
        people = int(match.group(1))

    year = None
    match = re.search(r"(19|20)\d{2}", q)

    if match:
        year = int(match.group())

    genre = None

    for vi, en in genre_map.items():
        if vi in q:
            genre = en
            break

    return {
        "intent": intent,
        "people": people,
        "year": year,
        "genre": genre,
    }


def suggest_room_type(people):
    if not people:
        return None

    if people <= 2:
        return "phòng đôi"

    return "phòng nhóm"


def enhance_query(query):
    info = parse_query(query)

    extra = ""

    if info["people"]:
        room_type = suggest_room_type(info["people"])
        extra += f"\nNgười dùng đi {info['people']} người → nên chọn {room_type}"

    if info["genre"]:
        extra += f"\nThể loại: {info['genre']}"

    if info["year"]:
        extra += f"\nNăm: {info['year']}"

    return query + "\n" + extra


def get_retriever(query):
    info = parse_query(query)

    if info["intent"] == "room":
        return vectordb.as_retriever(
            search_kwargs={
                "k": 2,
                "filter": {"type": "room"},
            }
        )

    if info["intent"] == "movie":
        return vectordb.as_retriever(
            search_kwargs={
                "k": 5,
                "filter": {"type": "movie"},
            }
        )

    return vectordb.as_retriever(
        search_kwargs={
            "k": 8,
        }
    )


# =========================================================
# 8. SIMPLE RECOMMENDATION FROM MONGODB
# =========================================================

def is_recommendation_query(query):
    q = query.lower()

    keywords = [
        "gợi ý",
        "đề xuất",
        "recommend",
        "recommendation",
        "phim hay",
        "nên xem",
        "tư vấn phim",
    ]

    return any(keyword in q for keyword in keywords)


def recommend_movies_from_mongo(query, limit=5):
    info = parse_query(query)

    candidates = []

    for m in movies:
        tconst = str(safe_meta(m.get("tconst"))).strip()
        title = str(safe_meta(m.get("primaryTitle"), "Không rõ tên")).strip()
        year = str(safe_meta(m.get("startYear"), "Không rõ năm")).strip()
        genres = str(safe_meta(m.get("genres"), "")).lower().strip()
        rating = to_float(m.get("averageRating"), 0)
        votes = to_int(m.get("numVotes"), 0)

        if not tconst or title == "Không rõ tên":
            continue

        if info["genre"] and info["genre"] not in genres:
            continue

        if info["year"] and str(info["year"]) != year:
            continue

        score = rating * 0.7 + min(votes / 100000, 1) * 3

        candidates.append({
            "title": title,
            "year": year,
            "genres": genres,
            "rating": rating,
            "votes": votes,
            "score": score,
            "url": f"/select-movie/{tconst}/",
            "tconst": tconst,
        })

    candidates.sort(
        key=lambda x: (
            x["score"],
            x["rating"],
            x["votes"],
        ),
        reverse=True,
    )

    return candidates[:limit]


def format_recommendation(movies_result):
    if not movies_result:
        return "Tôi chưa tìm thấy phim phù hợp để gợi ý."

    result = "Phim gợi ý:\n"

    for movie in movies_result:
        result += (
            f"- {movie['title']} "
            f"({movie['year']}) "
            f"- {movie['url']}\n"
        )

    return result.strip()


# =========================================================
# 9. PROMPT RAG
# =========================================================

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
Bạn là hệ thống truy xuất dữ liệu phim và phòng chiếu.

CHỈ được phép lấy thông tin từ CONTEXT.

TUYỆT ĐỐI KHÔNG:
- giải thích dài dòng
- dùng kiến thức ngoài dữ liệu
- tự bịa dữ liệu
- thêm lời chào
- thêm lời kết
- tạo phòng chiếu hoặc phim không có trong CONTEXT

Nếu CONTEXT không có dữ liệu phù hợp thì trả lời đúng:
"Tôi chưa tìm thấy phim hoặc phòng chiếu phù hợp."

BẮT BUỘC:
- Chỉ trả lời bằng tiếng Việt.
- Tên phim giữ nguyên như trong dữ liệu.
- Chỉ được trả về phim và phòng có trong dữ liệu.

FORMAT DUY NHẤT ĐƯỢC PHÉP:

Phim:
- tên phim (năm)

Phòng chiếu:
- tên phòng

CONTEXT:
{context}

CÂU HỎI:
{question}

TRẢ LỜI:
"""
)


# =========================================================
# 10. FASTAPI APP
# =========================================================

app = FastAPI()


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def home():
    return {
        "message": "Chatbot local API is running",
        "chat_endpoint": "/chat",
    }


@app.post("/chat")
def chat(req: ChatRequest):
    try:
        query = req.message.strip()

        if not query:
            return {
                "response": "Bạn chưa nhập nội dung câu hỏi.",
                "movies": [],
                "rooms": [],
            }
        # Nhánh RAG phim/phòng
        enhanced_query = enhance_query(query)
        retriever = get_retriever(query)

        qa = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            chain_type_kwargs={
                "prompt": prompt,
            },
            return_source_documents=True,
        )

        response = qa.invoke({
            "query": enhanced_query,
        })

        source_docs = response.get("source_documents", [])

        movies_result = []
        rooms_result = []

        for doc in source_docs:
            meta = doc.metadata

            if meta.get("type") == "movie":
                title = meta.get("title")
                year = meta.get("year")
                url = meta.get("url")
                tconst = meta.get("tconst")

                if title and url:
                    movies_result.append({
                        "title": title,
                        "year": year,
                        "url": url,
                        "tconst": tconst,
                    })

            elif meta.get("type") == "room":
                name = meta.get("name")
                url = meta.get("url")
                room_id = meta.get("room_id")
                status = meta.get("status")

                if name and url:
                    rooms_result.append({
                        "name": name,
                        "url": url,
                        "room_id": room_id,
                        "status": status,
                    })

        # Xóa trùng phim
        unique_movies = []
        seen_movie_urls = set()

        for movie in movies_result:
            if movie["url"] not in seen_movie_urls:
                unique_movies.append(movie)
                seen_movie_urls.add(movie["url"])

        # Xóa trùng phòng
        unique_rooms = []
        seen_room_urls = set()

        for room in rooms_result:
            if room["url"] not in seen_room_urls:
                unique_rooms.append(room)
                seen_room_urls.add(room["url"])

        result = ""

        if unique_movies:
            result += "Phim:\n"

            for movie in unique_movies[:5]:
                year_text = movie["year"] if movie["year"] else "Không rõ năm"

                result += (
                    f"- {movie['title']} "
                    f"({year_text}) "
                    f"- {movie['url']}\n"
                )

        if unique_rooms:
            result += "\nPhòng chiếu:\n"

            for room in unique_rooms[:2]:
                result += (
                    f"- {room['name']} "
                    f"- {room['url']}\n"
                )

        if not result.strip():
            result = "Tôi chưa tìm thấy phim hoặc phòng chiếu phù hợp."

        return {
            "response": result.strip(),
            "movies": unique_movies[:5],
            "rooms": unique_rooms[:2],
            "mode": "rag",
        }

    except Exception as e:
        return {
            "response": f"Lỗi chatbot: {str(e)}",
            "movies": [],
            "rooms": [],
        }
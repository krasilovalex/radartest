import json
import os

DB_PATH = "users.json"

def load_db():
    if not os.path.exists(DB_PATH):
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)





def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_user(user_id: int):
    data = load_db()
    if str(user_id) not in data:
        data[str(user_id)] = {
            "rating": 4.5,
            "rank" : {"min_points": 0, "ru": "👶 Новичок", "en": "👶 Beginner", "hi": "👶 नया"},  # словарь вместо строки
            "points": 0,  # добавляем очки
            "lang" : "",
            "verifed" : False
        } 
        save_db(data)

def get_user(user_id: int):
    data = load_db()
    return data.get(str(user_id))


def update_user(user_id: int, **kwargs):
    data = load_db()
    if str(user_id) in data:
        for k, v in kwargs.items():
            # не обновляем язык пустыми значениями
            if k == 'lang' and (v is None or v == ""):
                continue
            if v is not None:
                data[str(user_id)][k] = v
        save_db(data)

    

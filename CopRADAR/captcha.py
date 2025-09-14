import random
from PIL import Image, ImageDraw, ImageFont
import io

digits_patterns = {
    "0": [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    "1": [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
    "2": [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
    "3": [[1,1,1],[0,0,1],[0,1,1],[0,0,1],[1,1,1]],
    "4": [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
    "5": [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
    "6": [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
    "7": [[1,1,1],[0,0,1],[0,1,0],[0,1,0],[0,1,0]],
    "8": [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
    "9": [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
}


def generate_captcha():

    code = "".join([str(random.randint(0,9)) for _ in range(4)])
    img = Image.new("RGB", (300, 100), (255,255,255))
    draw = ImageDraw.Draw(img)

    # Параметры рисования кружков
    circle_size = 12
    spacing = 4
    digit_spacing = 20

    x_offset = 20
    for digit in code:
        pattern = digits_patterns[digit]
        for row_idx, row in enumerate(pattern):
            for col_idx, cell in enumerate(row):
                if cell:
                    cx = x_offset + col_idx * (circle_size + spacing)
                    cy = 20 + row_idx * (circle_size + spacing)
                    draw.ellipse((cx, cy, cx+circle_size, cy+circle_size), fill=(0,0,0))
        x_offset += len(pattern[0]) * (circle_size + spacing) + digit_spacing

    # Можно добавить лёгкий шум точками
    for _ in range(30):
        x1, y1 = random.randint(0,img.width), random.randint(0,img.height)
        draw.ellipse((x1,y1,x1+2,y1+2), fill=(100,100,100))
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)

    return code, img
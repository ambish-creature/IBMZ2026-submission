from io import BytesIO
from PIL import Image

def get_pillow_photo_object(data):
    img = Image.open(BytesIO(data))
    return(img)

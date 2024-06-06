# from fastapi import FastAPI, File, UploadFile, Request
# from fastapi.responses import RedirectResponse, FileResponse, Response
from flask import Flask
from flask import Flask, request, session, url_for, redirect, send_file, flash, render_template
from io import BytesIO
from werkzeug.utils import secure_filename
from zipfile36 import ZipFile
from PIL import Image, ImageOps, ExifTags

import models

ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
ALLOWED_ORIGINS = {
    'https://thijspeirelinck.be', 'https://www.thijspeirelinck.be',
    'http://127.0.0.1:4000', "https://personalwebsite.thijsp.repl.co",
    "http://127.0.0.1:5000"
}

app = Flask(__name__)
app.debug = True
app.secret_key = 'development key'
# app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
app.config['BOOTSTRAP_BOOTSWATCH_THEME'] = 'slate'


@app.route('/', methods=["GET"])
def home():
    # return redirect("https://thijspeirelinck.be")
    return render_template('index.html')


@app.route('/frameit-external-multiple', methods=["POST"])
def external_frameit_multiple():
    if request.method == 'POST':     # and request.environ['HTTP_ORIGIN'] in ALLOWED_ORIGINS:
        files = request.files.getlist('image')
        ratio = request.form.get('ratio')
        resolution = request.form.get('resolution')
        color = request.form.get('background')
        collage = request.form.get('collage')
        black_border = request.form.get('blackborder')
        all_files = []
        all_filenames = []
        if collage:
            buffers = []
            images = []
            for file in files:
                image_buffer, exif, image = buffer_from_file(file)
                buffers.append(image_buffer)
                if black_border:
                    image = models.add_black_border(image)
                images.append(image)
            img_with_border = models.collage(images, ratio, resolution, color)
            buffer = BytesIO()
            img_with_border.save(buffer, format='JPEG', exif=exif)
            buffer.seek(0)
            all_files.append(buffer)
            all_filenames.append('collage.jpg')
        else:
            for file in files:
                filename = check_filename(file)
                image_buffer, exif, image = buffer_from_file(file)
                img_with_border = models.img_border(image,
                                                    ratio,
                                                    resolution,
                                                    color,
                                                    black_border=black_border)
                imgs = img_with_border
                if not isinstance(img_with_border, list):
                    imgs = [img_with_border]
                for i, img_with_border in enumerate(imgs):
                    buffer = BytesIO()
                    img_with_border.save(buffer, format='JPEG', exif=exif)
                    buffer.seek(0)
                    all_files.append(buffer)
                    if len(imgs) == 1:
                        filen = get_filename(
                            filename) + '-framed.' + get_file_extension(
                            filename)
                    else:
                        filen = get_filename(filename) + '-framed' + '-' + str(
                            i + 1) + '.' + get_file_extension(filename)
                    all_filenames.append(filen)
        if len(all_filenames) == 1:
            return send_file(all_files[0],
                             as_attachment=True,
                             download_name=all_filenames[0],
                             mimetype='image/jpeg')
        stream = BytesIO()
        with ZipFile(stream, 'w') as zf:
            for i, image in enumerate(all_files):
                zf.writestr(all_filenames[i], all_files[i].getvalue())
        stream.seek(0)
        return send_file(stream,
                         as_attachment=True,
                         download_name='framed.zip',
                         mimetype='zip')
    return redirect("https://thijspeirelinck.be")


def allowed_file(filename):
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


def get_file_extension(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower()


def get_filename(filename):
    return '.' in filename and filename.rsplit('.', 1)[0]


def check_filename(file):
    filename = file.filename
    if 'file' not in request.files:
        redirect("https://thijspeirelinck.be/404")
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
    return filename


def buffer_from_file(file):
    b = BytesIO()
    image = Image.open(file)
    image = ImageOps.exif_transpose(image)
    exif = get_exif(image)
    image.save(b, format='jpeg')
    image_buffer = b.getbuffer().tobytes()
    return image_buffer, exif, image


def get_exif(image):
    exif = image.getexif()
    if exif is None:
        exif = Image.Exif()
    else:
        for k, v in exif.items():
            if k != 306 and k != 315 and k != 33432:
                del exif[k]
    exif[315] = 'Frame It'
    exif[305] = 'Frame It'
    XPKeywords = 0x9C9E
    exif[XPKeywords] = "Frame It;".encode("utf16")
    return exif


if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')

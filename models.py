import numpy as np
import matplotlib.colors as colors
from PIL import Image, ImageOps
import ffmpeg


def img_border(img,
               ratio='sq',
               resolution='best',
               color='#ffffff',
               min_pad=100,
               black_border=False):
    # if black border requested
    if black_border:
        img = add_black_border(img, color)
        min_pad = 10

    # if pano crop
    if ratio == 'pano_crop':
        return insta_pano_crop(img, ratio, resolution, color, min_pad,
                               black_border)

    # parse ratio and resolution
    ratio = parse_ratio(ratio)
    short_edge = parse_resolution(resolution)

    # define color
    # color = rgb_to_bgr(hex_to_rgb(color))

    # define border width and height
    img_width, img_height = img.size
    if img_width > img_height:
        new_width = img_width + min_pad * 2
        new_height = new_width // ratio[0] * ratio[1]
    else:
        if ratio[0] == 9:
            new_width = img_width + min_pad * 2
            new_height = new_width // ratio[0] * ratio[1]
            if new_height - img_height <= 0:
                new_height = img_height + min_pad * 2
                new_width = new_height // ratio[1] * ratio[0]
        else:
            new_height = img_height + min_pad * 2
            new_width = new_height // ratio[1] * ratio[0]
            if new_width - img_width <= 0:
                new_width = img_width + min_pad * 2
                new_height = new_width // ratio[0] * ratio[1]
    top = bottom = int((new_height - img_height) // 2)
    left = right = int((new_width - img_width) // 2)

    # create new image
    img_with_border = Image.new("RGB", (new_width, new_height), color=color)
    img_with_border.paste(img, (left, top))

    # resize image
    if short_edge:
        img_with_border = resize(img_with_border, short_edge)

    return img_with_border


def collage(img_files,
            ratio='sq',
            resolution='best',
            color='#ffffff',
            min_pad=120,
            stack_vertical=True,
            collage_only=False):
    background_color = hex_to_rgb(color)
    images = []  # array with all decodes images
    shapes = np.zeros((len(img_files), 2))  # array with tuples (height, width)
    for i, img in enumerate(img_files):
        images.append(img)
        w, h = img.size
        shapes[i, 0] = h
        shapes[i, 1] = w

    if ratio == '32' and not all_horizontal_images(shapes):
        stack_vertical = False
    if stack_vertical and all_vertical_images(shapes):
        stack_vertical = False

    # special case when there are 3 images of which only one is horizontal
    if len(images) == 3 and not collage_only:
        horizontal_idxs = 1.1 * shapes[:, 0] < shapes[:, 1]
        horizontal_img_files = []
        non_horizontal_img_files = []
        for i, idx in enumerate(horizontal_idxs):
            if idx:
                horizontal_img_files.append(img_files[i])
            else:
                non_horizontal_img_files.append(img_files[i])
        if np.array(horizontal_idxs).astype(int).sum() == 1:
            row1 = collage(non_horizontal_img_files, ratio, resolution, color,
                           min_pad, False, True)
            rows = [horizontal_img_files[0], row1]
            return collage(rows, ratio, resolution, color, min_pad, stack_vertical,
                           False)
        if np.array(horizontal_idxs).astype(int).sum() == 2 and ratio != 'vert':
            column1 = collage(horizontal_img_files, ratio, resolution, color,
                              min_pad, True, True)
            columns = [column1, non_horizontal_img_files[0]]
            return collage(columns, ratio, resolution, color, min_pad,
                           stack_vertical, False)

    # make multiple rows if there are more than 4 pictures
    if len(images) >= 4:
        # we will create two rows
        imgs_per_row = len(images) - len(images) // 2
        if ratio == '32':
            row_1 = collage(img_files[:imgs_per_row], ratio, resolution, color,
                            min_pad, True, True)
            row_2 = collage(img_files[imgs_per_row:], ratio, resolution, color,
                            min_pad, True, True)
            stack_vertical = True
        else:
            row_1 = collage(img_files[:imgs_per_row], ratio, resolution, color,
                            min_pad, stack_vertical, True)
            row_2 = collage(img_files[imgs_per_row:], ratio, resolution, color,
                            min_pad, stack_vertical, True)
        rows = [row_1, row_2]
        return collage(rows, ratio, resolution, color, min_pad, stack_vertical,
                       False)

    images, shapes = resize_collage(images, shapes, stack_vertical)

    # create empty matrix
    # in the case both pictures are vertical, they should be stacked horizontally
    nb_images = len(images)
    tot_height = int(shapes[:, 0].sum())
    max_width = int(shapes[:, 1].max())
    vis = np.zeros((tot_height + (nb_images - 1) * min_pad, max_width, 3),
                   np.uint8)
    if not stack_vertical:
        tot_width = int(shapes[:, 1].sum())
        max_height = int(shapes[:, 0].max())
        vis = np.zeros((max_height, tot_width + (nb_images - 1) * min_pad, 3),
                       np.uint8)

    # make sure the color of the pad equals the background color
    vis[:, :, 0] = background_color[0]
    vis[:, :, 1] = background_color[1]
    vis[:, :, 2] = background_color[2]

    # combine all images
    if not stack_vertical:
        for i, img in enumerate(images):
            h, w = int(shapes[i, 0]), int(shapes[i, 1])
            w_until_now = int(shapes[:i, 1].sum())
            pad_until_now = int(i * min_pad) if i > 0 else 0
            vis[:h, (w_until_now + pad_until_now):(w_until_now + w +
                                                   pad_until_now), :3] = img
    else:
        for i, img in enumerate(images):
            h, w = int(shapes[i, 0]), int(shapes[i, 1])
            h_until_now = int(shapes[:i, 0].sum())
            pad_until_now = int(i * min_pad) if i > 0 else 0
            vis[(h_until_now + pad_until_now):(h_until_now + h +
                                               pad_until_now), :w, :3] = img

    collage_img = Image.fromarray(vis)
    if collage_only:
        return collage_img
    return img_border(collage_img, ratio, resolution, color, min_pad)


def add_black_border(img, color='#ffffff'):
    """
      Add a border to the image.
    """
    img_width, img_height = img.size
    r = img_width / img_height
    print(r)
    if -0.001 < r - 16 / 9 < 0.001:
        border = Image.open("assets/horizontal/169-frameonly.tif")
        white_background = Image.new("RGB", (3840, 2160), color)
        img = resize(img, 2070)
    elif -0.001 < r - 3 / 2 < 0.001:
        border = Image.open("assets/horizontal/32-frameonly.tif")
        white_background = Image.new("RGB", (3840, 2560), color)
        img = resize(img, 2453)
    elif -0.001 < r - 2 / 1 < 0.001:
        border = Image.open("assets/horizontal/21-frameonly.tif")
        white_background = Image.new("RGB", (3840, 1920), color)
        img = resize(img, 1840)
    elif -0.001 < r - 5 / 4 < 0.001:
        border = Image.open("assets/horizontal/45-frameonly.tif")
        white_background = Image.new("RGB", (3840, 3072), color)
        img = resize(img, 2944)
    elif -0.001 < r - 4 / 3 < 0.001:
        border = Image.open("assets/horizontal/43-frameonly.tif")
        white_background = Image.new("RGB", (3840, 2880), color)
        img = resize(img, 2760)
    elif -0.001 < r - 9 / 16 < 0.001:
        border = Image.open("assets/vertical/169-frameonly.tif")
        white_background = Image.new("RGB", (2160, 3840), color)
        img = resize(img, 2070)
    elif -0.001 < r - 2 / 3 < 0.001:
        border = Image.open("assets/vertical/32-frameonly.tif")
        white_background = Image.new("RGB", (2560, 3840), color)
        img = resize(img, 2453)
    elif -0.001 < r - 1 / 2 < 0.001:
        border = Image.open("assets/vertical/21-frameonly.tif")
        white_background = Image.new("RGB", (1920, 3840), color)
        img = resize(img, 1840)
    elif -0.001 < r - 4 / 5 < 0.001:
        border = Image.open("assets/vertical/45-frameonly.tif")
        white_background = Image.new("RGB", (3072, 3840), color)
        img = resize(img, 2944)
    elif -0.001 < r - 3 / 4 < 0.001:
        border = Image.open("assets/vertical/43-frameonly.tif")
        white_background = Image.new("RGB", (2880, 3840), color)
        img = resize(img, 2760)
    else:
        border = Image.open("assets/horizontal/32-frameonly.tif")
        white_background = Image.new("RGB", (3840, 2560), color)
        img = resize(img, 2453)
    img_w, img_h = img.size
    bg_w, bg_h = white_background.size
    offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
    white_background.paste(img, offset)
    white_background.paste(border, (0, 0), border)
    img = white_background.convert('RGB')
    return img


def insta_pano_crop(img, ratio, resolution, color, min_pad, black_border):
    pano_ratio_width = 4 * 3
    pano_ratio_height = 5
    img_width, img_height = img.size
    if img_width / 8 * 5 == img_height:
        pano_ratio_width = 4 * 2
        pano_ratio_height = 5
    pano_width = int(img_height / pano_ratio_height * pano_ratio_width)
    pano_height = img_height
    background = Image.new("RGB", (pano_width, pano_height), color)
    bg_w, bg_h = background.size
    offset = ((bg_w - img_width) // 2, (bg_h - img_height) // 2)
    background.paste(img, offset)
    if pano_ratio_width == 8:
        imgs = create_grid(background, 2, 1)
    else:
        imgs = create_grid(background, 3, 1)
    return imgs


def video_border(video, rato='sq', color='#ffffff', min_pad=100, black_border=False, filename='framed'):
    inpt = ffmpeg.input(video)
    filen = filename + '.mp4'
    output = ffmpeg.output(inpt, filen, vcodec='libx264', vf='pad=w=iw+50:h=ih:x=25:y=0:color=white')

    output.run()


def resize_collage(images, shapes, stack_vertical):
    resized_images = []
    resized_shapes = np.zeros(shapes.shape)
    if not stack_vertical:
        min_height = int(np.min(shapes[:, 0]))
        for i, img in enumerate(images):
            h = shapes[i, 0]
            resized_img = img
            if h > min_height:
                w = shapes[i, 1]
                scale_factor = min_height / h
                dim = (int(w * scale_factor), min_height)
                resized_img = img.resize(dim, Image.LANCZOS)
            resized_images.append(resized_img)
            w, h = resized_img.size
            resized_shapes[i, 0] = h
            resized_shapes[i, 1] = w
    else:
        min_width = int(np.min(shapes[:, 1]))
        for i, img in enumerate(images):
            h = shapes[i, 0]
            w = shapes[i, 1]
            resized_img = img
            if w > min_width:
                scale_factor = min_width / w
                dim = (min_width, int(h * scale_factor))
                resized_img = img.resize(dim, Image.LANCZOS)
            resized_images.append(resized_img)
            w, h = resized_img.size
            resized_shapes[i, 0] = h
            resized_shapes[i, 1] = w
    return resized_images, resized_shapes


def all_vertical_images(shapes):
    return (shapes[:, 0] > 1.01 * shapes[:, 1]).all()


def all_horizontal_images(shapes):
    return (shapes[:, 0] < 1.01 * shapes[:, 1]).all()


def all_square_images(shapes):
    return not all_vertical_images(shapes) and not all_horizontal_images(shapes)


def resize(image, short_edge):
    # define the long edge of the original image (with border)
    img_width, img_height = image.size
    height_short, width_short = True, False
    img_short_edge = img_height
    if img_width < img_height:
        height_short, width_short = False, True
        img_short_edge = img_width

    # define the scale factor
    scale_factor = short_edge / img_short_edge

    # re-scale image
    width = int(img_width * scale_factor)
    height = int(img_height * scale_factor)
    dim = (width, height)

    # resize image
    resized = image.resize(dim, Image.LANCZOS)
    return resized


def parse_ratio(ratio_str):
    if ratio_str == 'sq':
        return 1, 1
    elif ratio_str == '45':
        return 4, 5
    elif ratio_str == '32':
        return 3, 2
    else:
        return 9, 16


def parse_resolution(resolution_str):
    """
      :param resolution_str: string representing the requested resolution
      :return: the short edge number of pixels or None for original short edge
      """
    if resolution_str == 'best':
        return None
    elif resolution_str == '4k':
        return 3840.
    else:
        return 1080.


def hex_to_rgb(hex_string):
    rgb = colors.hex2color(hex_string)
    return tuple([int(255 * x) for x in rgb])


def rgb_to_bgr(rgb):
    r, g, b = rgb
    return tuple([b, g, r])


def create_grid(img, nb_splits_horizontal, nb_splits_vertical=1):
    w, h = img.size
    crop_width = w // nb_splits_horizontal
    crop_height = h // nb_splits_vertical
    imgs = []
    for i in range(0, w, crop_width):
        for j in range(0, h, crop_height):
            box = (i, j, i + crop_width, j + crop_height)
            imgs.append(img.crop(box))
    if len(imgs) > nb_splits_horizontal * nb_splits_vertical:
        return imgs[:-1]
    return imgs

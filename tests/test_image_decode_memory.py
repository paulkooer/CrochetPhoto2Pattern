"""Decode without a full-size EXIF copy while retaining exact pixels and ownership."""
from io import BytesIO

import pytest
from PIL import Image, ImageDraw, ImageOps

from app.ui import uploads
from app.utils import images


class Upload(BytesIO):
    def __init__(self,blob):
        super().__init__(blob)
        self.size=len(blob)


def sample(mode="RGB",size=(81,53),orientation=None):
    canvas=Image.new("RGBA",size,(30,70,90,0))
    ImageDraw.Draw(canvas).rectangle((size[0]//4,size[1]//4,size[0]*3//4,size[1]*3//4),
                                    fill=(220,30,90,200))
    converted=canvas.convert(mode)
    buffer=BytesIO()
    kwargs={}
    if orientation is not None:
        exif=Image.Exif()
        exif[274]=orientation
        kwargs["exif"]=exif
    converted.save(buffer,format="JPEG" if orientation is not None else "PNG",**kwargs)
    return buffer.getvalue()


def old_pixels(blob):
    with Image.open(BytesIO(blob),formats=images.ALLOWED_UPLOAD_FORMATS) as original:
        if original.format=="JPEG":
            original.draft("RGB",(images.MAX_DECODED_SIDE,images.MAX_DECODED_SIDE))
        image=ImageOps.exif_transpose(original)
        image.thumbnail((images.MAX_DECODED_SIDE,images.MAX_DECODED_SIDE),Image.Resampling.LANCZOS)
        if image.mode in ("RGBA","LA","PA") or (image.mode=="P" and "transparency" in image.info):
            rgba=image.convert("RGBA")
            image=Image.alpha_composite(Image.new("RGBA",rgba.size,"white"),rgba).convert("RGB")
        return image.mode,image.size,image.tobytes()


@pytest.mark.parametrize("orientation",range(1,9))
def test_all_exif_orientations_keep_pixels_across_three_loaders_and_closed_inputs(tmp_path,orientation):
    check_loaders(tmp_path,sample(orientation=orientation))


@pytest.mark.parametrize("mode",["RGB","RGBA","LA","L","P"])
def test_png_modes_keep_pixels_across_three_loaders_and_closed_inputs(tmp_path,mode):
    check_loaders(tmp_path,sample(mode))


def check_loaders(tmp_path,blob):
    expected=old_pixels(blob)
    path=tmp_path/"input.img"
    path.write_bytes(blob)
    upload=Upload(blob)
    results=[images.load_image_bytes(blob),images.load_image_file(path),uploads.load_uploaded_image(upload)]
    assert not upload.closed
    upload.close()
    path.unlink()
    for result in results:
        assert result is not None
        assert (result.mode,result.size,result.tobytes())==expected
        assert result.copy().getpixel((0,0))==result.getpixel((0,0))


def test_large_rgba_downsampling_remains_pixel_identical(tmp_path):
    check_loaders(tmp_path,sample("RGBA",(3000,2100)))


def test_unoriented_large_image_never_clones_full_size_before_downsampling(tmp_path,monkeypatch):
    blob=sample("RGB",(3000,2100))
    original=Image.Image.copy
    sizes=[]
    def bounded_copy(image):
        sizes.append(image.size)
        assert max(image.size)<=images.MAX_DECODED_SIDE
        return original(image)
    monkeypatch.setattr(Image.Image,"copy",bounded_copy)
    path=tmp_path/"large.png"
    path.write_bytes(blob)
    for result in (images.load_image_bytes(blob),images.load_image_file(path),
                   uploads.load_uploaded_image(Upload(blob))):
        assert result is not None and max(result.size)==images.MAX_DECODED_SIDE
    assert sizes


def test_pixel_guard_rejects_before_any_decoder_load(tmp_path,monkeypatch):
    blob=sample()
    path=tmp_path/"input.png"
    path.write_bytes(blob)
    monkeypatch.setattr(images,"MAX_UPLOAD_PIXELS",100)
    def forbidden_load(*args,**kwargs):
        pytest.fail("must reject dimensions before decoding")
    monkeypatch.setattr(Image.Image,"load",forbidden_load)
    assert images.load_image_bytes(blob) is None
    assert images.load_image_file(path) is None
    assert uploads.load_uploaded_image(Upload(blob)) is None
